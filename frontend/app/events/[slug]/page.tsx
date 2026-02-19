import { notFound, redirect } from "next/navigation";

import { EventVariantDetail } from "@/components/events/event-variant-detail";
import { getEvent, getEventAttendees } from "@/lib/api/queries";
import { ensureModuleEnabled } from "@/lib/module-guards";

interface EventDetailPageProps {
  params: Promise<{
    slug: string;
  }>;
}

export default async function EventDetailPage({ params }: EventDetailPageProps) {
  await ensureModuleEnabled("events");
  const { slug } = await params;
  const [event, attendeeData] = await Promise.all([
    getEvent(slug).catch(() => null),
    getEventAttendees(slug).catch(() => null),
  ]);
  if (!event) {
    notFound();
  }
  if (event.redirect_link) {
    redirect(event.redirect_link);
  }
  return <EventVariantDetail event={event} attendeeData={attendeeData} />;
}
