import { EventVariantHeader } from "@/components/events/event-variant-header";
import {
  EventVariantAttendeeSection,
  EventVariantMainAndPages,
  EventVariantSignupSection,
} from "@/components/events/event-variant-sections";
import { EventDetailShell } from "@/components/events/event-detail-shell";
import {
  type SectionKey,
  type VariantNavItem,
} from "@/components/events/event-variant-helpers";
import type { EventAttendeeListPayload, EventItem } from "@/lib/api/types";
import styles from "./event-variant-themed.module.css";

interface EventVariantThemedProps {
  event: EventItem;
  attendeeData: EventAttendeeListPayload | null;
  projectName?: string;
  navItems: VariantNavItem[];
  activeSection: SectionKey | "none";
  showMain: boolean;
  showSignup: boolean;
  showAttendees: boolean;
  onSectionSelect: (section: SectionKey) => void;
  sectionHash: (section: SectionKey) => string;
}

export function EventVariantThemed({
  event,
  attendeeData,
  projectName,
  navItems,
  activeSection,
  showMain,
  showSignup,
  showAttendees,
  onSectionSelect,
  sectionHash,
}: EventVariantThemedProps) {
  const variant = event.template_variant ?? "default";
  const isONArsfest = variant === "arsfest" && projectName?.toLowerCase() === "on";
  const variantContentClass = styles.content;
  const variantRootClass =
    variant === "arsfest"
      ? styles.variantArsfest
      : variant === "baal"
        ? styles.variantBaal
        : variant === "wappmiddag"
          ? styles.variantWappmiddag
          : variant === "kk100"
            ? styles.variantKk100
            : "";
  const pageClassName = `event-detail-page event-variant-shell event-variant--${variant} ${styles.pageRoot} ${variantRootClass}`;
  const backgroundClassName = `event-detail-background background-img ${event.image_url ? "has-image" : ""}`;
  const containerClassName = `container-size event-detail-container ${styles.container} ${
    variant === "arsfest" ? styles.lavaContainerBottom : ""
  }`;

  return (
    <EventDetailShell
      pageClassName={pageClassName}
      backgroundClassName={backgroundClassName}
      containerClassName={containerClassName}
      backgroundImageUrl={event.image_url}
    >
      <EventVariantHeader
        event={event}
        projectName={projectName}
        navItems={navItems}
        activeSection={activeSection}
        onSectionSelect={onSectionSelect}
        sectionHash={sectionHash}
        isONArsfest={isONArsfest}
      />

      <EventVariantMainAndPages
        event={event}
        variantContentClass={variantContentClass}
        showMain={showMain}
        activeSection={activeSection}
      />

      <EventVariantSignupSection
        event={event}
        variantContentClass={variantContentClass}
        showSignup={showSignup}
      />

      <EventVariantAttendeeSection
        attendeeData={attendeeData}
        variantContentClass={variantContentClass}
        showAttendees={showAttendees}
      />
    </EventDetailShell>
  );
}
