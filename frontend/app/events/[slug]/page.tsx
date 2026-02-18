import { notFound } from "next/navigation";

import { EventVariantDetail } from "@/components/events/event-variant-detail";
import { getEvent, getEventAttendees } from "@/lib/api/queries";
import { ensureModuleEnabled } from "@/lib/module-guards";

interface EventDetailPageProps {
  params: {
    slug: string;
  };
}

export default async function EventDetailPage({ params }: EventDetailPageProps) {
  await ensureModuleEnabled("events");
  const { slug } = params;
  const [event, attendeeData] = await Promise.all([
    getEvent(slug).catch(() => null),
    getEventAttendees(slug).catch(() => null),
  ]);
  if (!event) {
    notFound();
  }
  return <EventVariantDetail event={event} attendeeData={attendeeData} />;
}
