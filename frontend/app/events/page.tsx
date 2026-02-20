import { EventsIndexView } from "@/features/events/events-index-view";
import { getEvents, getSiteMeta } from "@/lib/api/queries";
import { ensureModuleEnabled } from "@/lib/module-guards";

export default async function EventsPage() {
  await ensureModuleEnabled("events");
  const [upcomingEvents, allEvents, siteMeta] = await Promise.all([
    getEvents(false),
    getEvents(true),
    getSiteMeta().catch(() => null),
  ]);
  const upcomingEventSlugs = new Set(upcomingEvents.map((event) => event.slug));
  const pastEvents = allEvents
    .filter((event) => !upcomingEventSlugs.has(event.slug))
    .sort((left, right) => new Date(right.event_date_start).getTime() - new Date(left.event_date_start).getTime());

  const isON = siteMeta?.project_name?.toLowerCase() === "on";

  return <EventsIndexView upcomingEvents={upcomingEvents} pastEvents={pastEvents} isON={isON} />;
}
