import { redirect } from "next/navigation";

export default function MembersInfoRedirectPage() {
  redirect("/members/profile");
}
