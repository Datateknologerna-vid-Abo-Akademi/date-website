"use client";

import { EventVariantDefault } from "@/components/events/event-variant-default";
import { EventVariantThemed } from "@/components/events/event-variant-themed";
import { EventVariantTomtejakt } from "@/components/events/event-variant-tomtejakt";
import { useEventVariantNavigation } from "@/components/events/use-event-variant-navigation";
import type { EventAttendeeListPayload, EventItem } from "@/lib/api/types";

interface EventVariantDetailProps {
  event: EventItem;
  attendeeData: EventAttendeeListPayload | null;
  projectName?: string;
}


export function EventVariantDetail({ event, attendeeData, projectName }: EventVariantDetailProps) {
  const {
    activeSection,
    isSpecialVariant,
    navItems,
    onSectionSelect,
    sectionHash,
    showAttendees,
    showMain,
    showSignup,
    variant,
  } = useEventVariantNavigation({ event });

  if (!isSpecialVariant) {
    return <EventVariantDefault event={event} attendeeData={attendeeData} projectName={projectName} />;
  }

  if (variant === "tomtejakt") {
    return <EventVariantTomtejakt event={event} attendeeData={attendeeData} />;
  }

  return (
    <EventVariantThemed
      event={event}
      attendeeData={attendeeData}
      projectName={projectName}
      navItems={navItems}
      activeSection={activeSection}
      showMain={showMain}
      showSignup={showSignup}
      showAttendees={showAttendees}
      onSectionSelect={onSectionSelect}
      sectionHash={sectionHash}
    />
  );
}
