"use client";

import { FormEvent, useState } from "react";

import { mutateApi } from "@/lib/api/client";
import type { PollQuestion } from "@/lib/api/types";
import formStyles from "@/components/ui/form-primitives.module.css";
import listStyles from "@/components/ui/list-primitives.module.css";

interface PollVoteFormProps {
  initialPoll: PollQuestion;
}

export function PollVoteForm({ initialPoll }: PollVoteFormProps) {
  const [poll, setPoll] = useState(initialPoll);
  const [selectedChoices, setSelectedChoices] = useState<number[]>([]);
  const [errorMessage, setErrorMessage] = useState("");
  const [statusMessage, setStatusMessage] = useState("");
  const isMultiple = poll.multiple_choice;

  function toggleChoice(choiceId: number) {
    if (!isMultiple) {
      setSelectedChoices([choiceId]);
      return;
    }
    setSelectedChoices((previous) =>
      previous.includes(choiceId)
        ? previous.filter((choice) => choice !== choiceId)
        : [...previous, choiceId],
    );
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErrorMessage("");
    setStatusMessage("");
    try {
      const updatedPoll = await mutateApi<PollQuestion>({
        method: "POST",
        path: `polls/${poll.id}/vote`,
        body: { choice_ids: selectedChoices },
      });
      setPoll(updatedPoll);
      setSelectedChoices([]);
      setStatusMessage("Vote recorded.");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Vote failed");
    }
  }

  return (
    <div className={formStyles.stack}>
      <form className={formStyles.stack} onSubmit={onSubmit}>
        <fieldset className={formStyles.fieldset}>
          <legend>{poll.question_text}</legend>
          {poll.choices.map((choice) => (
            <label key={choice.id} className={formStyles.choiceLine}>
              <input
                type={isMultiple ? "checkbox" : "radio"}
                name={`poll-${poll.id}`}
                checked={selectedChoices.includes(choice.id)}
                onChange={() => toggleChoice(choice.id)}
              />
              <span>{choice.choice_text}</span>
            </label>
          ))}
        </fieldset>
        <button type="submit">Submit vote</button>
      </form>
      {errorMessage ? <p className="form-error">{errorMessage}</p> : null}
      {statusMessage ? <p className="form-success">{statusMessage}</p> : null}
      {poll.show_results || statusMessage ? (
        <div>
          <h3>Results ({poll.total_votes} votes)</h3>
          <ul className={listStyles.list}>
            {poll.choices.map((choice) => (
              <li key={choice.id}>
                {choice.choice_text}: {choice.votes} ({choice.vote_percentage}%)
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
