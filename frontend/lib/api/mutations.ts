import { apiClient } from "./openapi-client";
import { ApiRequestError } from "./queries";

export async function unwrapMutation<T>(promise: Promise<{ data?: T; error?: unknown }>): Promise<T> {
    const { data, error } = await promise;
    if (error) {
        const errObj = (error as Record<string, unknown>) || ({} as Record<string, unknown>);
        throw new ApiRequestError({
            message: (errObj.message as string) || (errObj.detail as string) || "API Error",
            status: 400,
            details: errObj.details || errObj,
            code: (errObj.code as string) || "unknown_error",
        });
    }
    return data as T;
}

// -- AUTH MUTATIONS --

export type LoginPayload = { username?: string; password?: string };
export async function loginUser(payload: LoginPayload) {
    return unwrapMutation(apiClient.POST("/api/v1/auth/login", { body: payload }));
}

export async function logoutUser() {
    return unwrapMutation(apiClient.POST("/api/v1/auth/logout"));
}

export type SignupPayload = Record<string, unknown>; // fallback if schema missing
export async function signupUser(payload: SignupPayload) {
    return unwrapMutation(apiClient.POST("/api/v1/auth/signup", { body: payload }));
}

export type PasswordChangePayload = { old_password?: string; new_password1?: string; new_password2?: string };
export async function changePassword(payload: PasswordChangePayload) {
    return unwrapMutation(apiClient.POST("/api/v1/auth/password-change", { body: payload }));
}

export type PasswordResetPayload = { email?: string };
export async function resetPassword(payload: PasswordResetPayload) {
    return unwrapMutation(apiClient.POST("/api/v1/auth/password-reset", { body: payload }));
}

export type PasswordResetConfirmPayload = { new_password1?: string; new_password2?: string };
export async function confirmPasswordReset(uid: string, token: string, payload: PasswordResetConfirmPayload) {
    return unwrapMutation(
        apiClient.POST("/api/v1/auth/password-reset/{uidb64}/{token}", {
            params: { path: { uidb64: uid, token } },
            body: payload,
        })
    );
}

// -- PROFILE & FUNCTIONARY MUTATIONS --

export type ProfileUpdatePayload = Record<string, unknown>;
export async function updateProfile(payload: ProfileUpdatePayload) {
    return unwrapMutation(apiClient.PATCH("/api/v1/members/me", { body: payload }));
}

export async function addFunctionaryRole(roleId: number, year: number) {
    return unwrapMutation(
        apiClient.POST("/api/v1/members/me/functionaries", {
            body: { functionary_role_id: roleId, year },
        })
    );
}

export async function deleteFunctionaryRole(id: number) {
    return unwrapMutation(
        apiClient.DELETE("/api/v1/members/me/functionaries/{functionary_id}", {
            params: { path: { functionary_id: id } },
        })
    );
}

// -- ALUMNI MUTATIONS --

export async function signupAlumni(payload: Record<string, unknown>) {
    return unwrapMutation(apiClient.POST("/api/v1/alumni/signup", { body: payload }));
}

export async function requestAlumniUpdate(email: string, captchaToken: string) {
    return unwrapMutation(
        apiClient.POST("/api/v1/alumni/update", {
            body: { email, "cf-turnstile-response": captchaToken },
        })
    );
}

export async function updateAlumni(token: string, payload: Record<string, unknown>) {
    return unwrapMutation(
        apiClient.POST("/api/v1/alumni/update/{token}", {
            params: { path: { token } },
            body: payload,
        })
    );
}

// -- EVENTS & CTF & POLLS MUTATIONS --

export async function submitHarassment(payload: Record<string, unknown>) {
    return unwrapMutation(apiClient.POST("/api/v1/social/harassment", { body: payload }));
}

export async function votePoll(pollId: number, choiceIds: number[]) {
    return unwrapMutation(
        // @ts-expect-error fallback path signature
        apiClient.POST("/api/v1/polls/{id}/vote", {
            params: { path: { id: pollId } },
            body: { choice_ids: choiceIds },
        })
    );
}

export async function guessCtfFlag(ctfSlug: string, flagSlug: string, guess: string) {
    return unwrapMutation(
        // @ts-expect-error fallback path signature
        apiClient.POST("/api/v1/ctf/{slug}/{flag}/guess", {
            params: { path: { slug: ctfSlug, flag: flagSlug } },
            body: { guess },
        })
    );
}

export async function verifyEventPasscode(eventSlug: string, passcode: string) {
    return unwrapMutation(
        apiClient.POST("/api/v1/events/{slug}/passcode", {
            params: { path: { slug: eventSlug } },
            body: { passcode },
        })
    );
}

export async function signupEvent(eventSlug: string, payload: Record<string, unknown>) {
    return unwrapMutation(
        apiClient.POST("/api/v1/events/{slug}/signup", {
            params: { path: { slug: eventSlug } },
            body: payload,
        })
    );
}
