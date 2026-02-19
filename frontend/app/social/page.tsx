import { ensureModuleEnabled } from "@/lib/module-guards";

export default async function SocialPage() {
  await ensureModuleEnabled("social");

  return (
    <div className="container-md min-vh-100 container-margin-top p-1">
      <div className="container-size break-words" />
    </div>
  );
}
