/* eslint-disable @next/next/no-img-element */
import {
  variantHeading,
  type SectionKey,
  type VariantNavItem,
} from "@/components/events/event-variant-helpers";
import type { EventItem } from "@/lib/api/types";
import styles from "./event-variant-themed.module.css";

interface EventVariantHeaderProps {
  event: EventItem;
  projectName?: string;
  navItems: VariantNavItem[];
  activeSection: SectionKey | "none";
  onSectionSelect: (section: SectionKey) => void;
  sectionHash: (section: SectionKey) => string;
  isONArsfest: boolean;
}

export function EventVariantHeader({
  event,
  projectName,
  navItems,
  activeSection,
  onSectionSelect,
  sectionHash,
  isONArsfest,
}: EventVariantHeaderProps) {
  const variant = event.template_variant ?? "default";
  const usesArsfestNav = variant === "arsfest" && !isONArsfest;
  const linkClass = usesArsfestNav ? styles.ballLink : styles.baalLink;

  return (
    <div className={`${styles.content} ${styles.headerBox}`}>
      {variant === "arsfest" ? (
        <div className={styles.mainContent}>
          <div className={styles.flexCenter}>
            {projectName?.toLowerCase() === "on" ? (
              <>
                <img
                  style={{ marginBottom: "30px" }}
                  className="pentalbin"
                  src="/static/core/images/footerlogo.png"
                  alt="ÖNs logo"
                />
                <h1 className={`age ${styles.cardShineEffect}`}>{event.title}</h1>
              </>
            ) : (
              <div className={`${styles.periodicTableSquare} ${styles.glowingTextOrange}`}>
                <div className={styles.periodicTableInner}>
                  <div className={`${styles.periodicTableNumberContainer} ${styles.cardShineEffect}`}>
                    <h2>26</h2>
                  </div>
                  <h2 className={`age ${styles.cardShineEffect}`}>DaTe</h2>
                  <div className={`${styles.periodicTableDateContainer} ${styles.cardShineEffect}`}>
                    <h2>Årsfest 22.2.2025</h2>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      ) : variant === "wappmiddag" ? (
        <>
          <img className={`${styles.balloon} ${styles.balloonLeft}`} src="/static/core/images/ballong_black.png" alt="balloon" />
          <img className={`${styles.balloon} ${styles.balloonRight}`} src="/static/core/images/ballong_black.png" alt="balloon" />
          <img
            className={`${styles.headerLogo} ${styles.wappmiddagHeaderLogo}`}
            src="/static/events/img/wappmiddag-header.svg"
            alt=""
            aria-hidden="true"
          />
          <h1 className={styles.baalHeader}>{variantHeading(event.template_variant)}</h1>
        </>
      ) : (
        <>
          {variant === "baal" ? (
            <img className={styles.headerLogo} src="/static/core/images/HQKK_2.png" alt={variantHeading(event.template_variant)} />
          ) : null}
          {variant === "kk100" ? (
            <img className={styles.headerLogo} src="/static/core/images/100logogold.png" alt={variantHeading(event.template_variant)} />
          ) : null}
          {variantHeading(event.template_variant) ? <h1 className={styles.baalHeader}>{variantHeading(event.template_variant)}</h1> : null}
        </>
      )}

      {navItems.length > 0 ? (
        <div className={`${styles.nav} ${usesArsfestNav ? styles.flexCenter : ""}`}>
          {navItems.map((item) => (
            <a
              key={item.key}
              className={`${styles.navLink} ${linkClass} ${activeSection === item.key ? styles.navLinkActive : ""}`}
              href={sectionHash(item.key)}
              onClick={(domEvent) => {
                domEvent.preventDefault();
                onSectionSelect(item.key);
              }}
            >
              {item.label}
            </a>
          ))}
        </div>
      ) : null}
    </div>
  );
}
