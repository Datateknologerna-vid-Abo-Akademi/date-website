"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

import { getApiClient, mutateApi } from "@/lib/api/client";
import type { FunctionaryItem, FunctionaryRole } from "@/lib/api/types";
import styles from "./functionary-manager.module.css";

interface FunctionaryManagerProps {
  initialYear: number;
}

export function FunctionaryManager({ initialYear }: FunctionaryManagerProps) {
  const [myFunctionaries, setMyFunctionaries] = useState<FunctionaryItem[]>([]);
  const [roles, setRoles] = useState<FunctionaryRole[]>([]);
  const [roleId, setRoleId] = useState<number | "">("");
  const [year, setYear] = useState(initialYear);
  const [errorMessage, setErrorMessage] = useState("");
  const [statusMessage, setStatusMessage] = useState("");

  const hasRoles = useMemo(() => roles.length > 0, [roles]);

  useEffect(() => {
    async function loadData() {
      try {
        const [currentFunctionaries, availableRoles] = await Promise.all([
          getApiClient<FunctionaryItem[]>("members/me/functionaries"),
          getApiClient<FunctionaryRole[]>("members/functionary-roles"),
        ]);
        setMyFunctionaries(currentFunctionaries);
        setRoles(availableRoles);
        if (availableRoles.length > 0) setRoleId(availableRoles[0].id);
      } catch (error) {
        setErrorMessage(error instanceof Error ? error.message : "Failed loading functionaries");
      }
    }
    void loadData();
  }, []);

  async function onCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErrorMessage("");
    setStatusMessage("");
    if (roleId === "") return;
    try {
      const created = await mutateApi<FunctionaryItem>({
        method: "POST",
        path: "members/me/functionaries",
        body: { functionary_role_id: roleId, year },
      });
      setMyFunctionaries((previous) => [created, ...previous]);
      setStatusMessage("Functionary role added.");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to add functionary role");
    }
  }

  async function onDelete(functionaryId: number) {
    setErrorMessage("");
    setStatusMessage("");
    try {
      await mutateApi<void>({
        method: "DELETE",
        path: `members/me/functionaries/${functionaryId}`,
      });
      setMyFunctionaries((previous) => previous.filter((item) => item.id !== functionaryId));
      setStatusMessage("Functionary role removed.");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to remove functionary role");
    }
  }

  return (
    <div className={styles.container}>
      <form className={styles.actions} onSubmit={onCreate}>
        <label className="form-field">
          <span>Role</span>
          <select
            value={roleId}
            onChange={(event) => setRoleId(event.target.value ? Number(event.target.value) : "")}
            disabled={!hasRoles}
          >
            {roles.map((role) => (
              <option key={role.id} value={role.id}>
                {role.title}
              </option>
            ))}
          </select>
        </label>
        <label className="form-field">
          <span>Year</span>
          <input type="number" value={year} onChange={(event) => setYear(Number(event.target.value))} />
        </label>
        <button type="submit" disabled={!hasRoles}>
          Add role
        </button>
      </form>
      {errorMessage ? <p className="form-error">{errorMessage}</p> : null}
      {statusMessage ? <p className="form-success">{statusMessage}</p> : null}
      <ul className={styles.list}>
        {myFunctionaries.map((functionary) => (
          <li key={functionary.id} className={styles.row}>
            <span>
              {functionary.year} - {functionary.functionary_role.title}
            </span>
            <button type="button" onClick={() => onDelete(functionary.id)}>
              Delete
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
