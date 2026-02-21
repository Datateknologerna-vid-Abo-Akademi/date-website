"use client";

import { FormEvent, useMemo, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

import { getApiClient, mutateApi } from "@/lib/api/client";
import type { FunctionaryItem, FunctionaryRole } from "@/lib/api/types";
import styles from "./functionary-manager.module.css";

interface FunctionaryManagerProps {
  initialYear: number;
}

export function FunctionaryManager({ initialYear }: FunctionaryManagerProps) {
  const queryClient = useQueryClient();
  const [roleId, setRoleId] = useState<number | "">("");
  const [year, setYear] = useState(initialYear);

  const { data: myFunctionaries = [], isLoading: loadingFunctionaries } = useQuery({
    queryKey: ["functionaries"],
    queryFn: () => getApiClient<FunctionaryItem[]>("members/me/functionaries"),
  });

  const { data: roles = [], isLoading: loadingRoles } = useQuery({
    queryKey: ["functionary-roles"],
    queryFn: () => getApiClient<FunctionaryRole[]>("members/functionary-roles"),
  });

  const hasRoles = useMemo(() => roles.length > 0, [roles]);

  const addMutation = useMutation({
    mutationFn: async () => {
      if (roleId === "") throw new Error("Please select a role");
      return mutateApi<FunctionaryItem>({
        method: "POST",
        path: "members/me/functionaries",
        body: { functionary_role_id: roleId, year },
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["functionaries"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: number) => {
      return mutateApi<void>({
        method: "DELETE",
        path: `members/me/functionaries/${id}`,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["functionaries"] });
    },
  });

  async function onCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    addMutation.mutate();
  }

  async function onDelete(functionaryId: number) {
    deleteMutation.mutate(functionaryId);
  }

  return (
    <div className={styles.container}>
      <form className={styles.actions} onSubmit={onCreate}>
        <label className="form-field">
          <span>Role</span>
          <select
            value={roleId}
            onChange={(event) => setRoleId(event.target.value ? Number(event.target.value) : "")}
            disabled={!hasRoles || loadingRoles || addMutation.isPending}
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
          <input type="number" value={year} onChange={(event) => setYear(Number(event.target.value))} disabled={addMutation.isPending} />
        </label>
        <button type="submit" disabled={!hasRoles || addMutation.isPending}>
          {addMutation.isPending ? "Adding..." : "Add role"}
        </button>
      </form>
      {addMutation.error || deleteMutation.error ? <p className="form-error">{(addMutation.error || deleteMutation.error)?.message}</p> : null}
      {addMutation.isSuccess && !addMutation.isPending ? <p className="form-success">Functionary role added.</p> : null}
      {deleteMutation.isSuccess && !deleteMutation.isPending ? <p className="form-success">Functionary role removed.</p> : null}

      {loadingFunctionaries ? <p>Loading functionaries...</p> : null}
      <ul className={styles.list}>
        {myFunctionaries.map((functionary) => (
          <li key={functionary.id} className={styles.row}>
            <span>
              {functionary.year} - {functionary.functionary_role.title}
            </span>
            <button type="button" onClick={() => onDelete(functionary.id)} disabled={deleteMutation.isPending}>
              {deleteMutation.isPending && deleteMutation.variables === functionary.id ? "Deleting..." : "Delete"}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
