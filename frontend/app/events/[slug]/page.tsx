import { notFound, redirect } from "next/navigation";

import { EventVariantDetail } from "@/components/events/event-variant-detail";
import { getEvent, getEventAttendees, getSiteMeta, ApiRequestError } from "@/lib/api/queries";
import { ensureModuleEnabled } from "@/lib/module-guards";

interface EventDetailPageProps {
  params: Promise<{
    slug: string;
  }>;
}

export default async function EventDetailPage({ params }: EventDetailPageProps) {
  await ensureModuleEnabled("events");
  const { slug } = await params;
  const eventPath = `/events/${slug}`;

  const isLoginRequiredError = (error: unknown) =>
    error instanceof ApiRequestError &&
    error.status === 403 &&
    (error.code === "forbidden" || error.code === "unauthenticated");

  const [event, attendeeData, siteMeta] = await Promise.all([
    getEvent(slug).catch((error) => {
      if (isLoginRequiredError(error)) {
        redirect(`/members/login?next=${encodeURIComponent(eventPath)}`);
      }
      return null;
    }),
    getEventAttendees(slug).catch(() => null),
    getSiteMeta().catch(() => null),
  ]);
  if (!event) {
    notFound();
  }
  if (event.redirect_link) {
    redirect(event.redirect_link);
  }
  return (
    <EventVariantDetail
      event={event}
      attendeeData={attendeeData}
      projectName={siteMeta?.project_name}
    />
  );
}
