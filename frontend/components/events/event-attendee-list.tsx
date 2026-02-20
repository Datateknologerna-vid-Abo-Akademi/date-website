import type { EventAttendeeListPayload } from "@/lib/api/types";
import styles from "./event-attendee-list.module.css";

interface EventAttendeeListProps {
  data: EventAttendeeListPayload | null;
  useVariantTemplateCopy?: boolean;
}

export function EventAttendeeList({ data, useVariantTemplateCopy = false }: EventAttendeeListProps) {
  if (!data) {
    return <h4 id="no-attendee">Deltagarlistan är inte tillgänglig just nu.</h4>;
  }
  if (!data.show_attendee_list) {
    return <h4 id="no-attendee">Deltagarlistan är dold för tidigare evenemang.</h4>;
  }

  const headingTag = useVariantTemplateCopy ? "h1" : "h2";
  const headingText = "Anmälda";
  const emptyText = useVariantTemplateCopy
    ? "Inga anmälda, var den första att anmäla dig!"
    : "Inga anmälda ännu, var den första!";

  if (data.attendees.length === 0) {
    return (
      <div className={styles.tableWrap}>
        {data.sign_up_max_participants !== 0 ? <p>Det finns {data.sign_up_max_participants} platser!</p> : null}
        {headingTag === "h1" ? <h1>{headingText}</h1> : <h2>{headingText}</h2>}
        <p id="no-attendee">{emptyText}</p>
      </div>
    );
  }

  return (
    <div className={styles.tableWrap}>
      {data.sign_up_max_participants !== 0 ? <p>Det finns {data.sign_up_max_participants} platser!</p> : null}
      {headingTag === "h1" ? <h1>{headingText}</h1> : <h2>{headingText}</h2>}
      <table className={styles.attendeeTable} id="attendees">
        <thead>
          <tr id="attendees-header" className={styles.attendeesHeader}>
            <th>#</th>
            <th>Namn</th>
            {data.registration_public_fields.map((fieldName) => (
              <th key={fieldName}>{fieldName}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.attendees.map((attendee) => (
            <tr key={`${attendee.position}-${attendee.display_name}`} className={attendee.is_waitlist ? "is-waitlist" : ""}>
              <td>{attendee.position}</td>
              <td>{attendee.display_name}</td>
              {attendee.fields.map((field) => (
                <td key={`${attendee.position}-${field.name}`}>{field.value}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
