/* eslint-disable @next/next/no-img-element */
import styles from "./home-hero.module.css";

interface HomeHeroProps {
  brand: string;
  associationName: string;
  heroSubtitle: string;
  heroLogo: string;
  inlineHeroLogo: string;
}

export function HomeHero({
  brand,
  associationName,
  heroSubtitle,
  heroLogo,
  inlineHeroLogo,
}: HomeHeroProps) {
  const isKkBrand = brand === "kk";
  const isBiocumBrand = brand === "biocum";
  const rootClassName = [
    styles.pathAnim,
    isKkBrand ? styles.brandKk : "",
    isBiocumBrand ? styles.brandBiocum : "",
  ]
    .filter(Boolean)
    .join(" ");

  if (isBiocumBrand) {
    return (
      <header className={`${styles.header} header wave home-hero-legacy ${rootClassName}`}>
        <div className={`${styles.scalingSvgContainer} scaling-svg-container home-hero-logo-wrap ${styles.logoWrap}`}>
          {inlineHeroLogo ? (
            <div
              className={`home-hero-logo-inline home-hero-logo-inline--animated ${styles.logoInline}`}
              aria-hidden="true"
              dangerouslySetInnerHTML={{ __html: inlineHeroLogo }}
            />
          ) : (
            <img
              src={heroLogo}
              alt={associationName}
              className={`home-hero-logo home-hero-logo--animated ${styles.logo} ${styles.logoAnimated}`}
            />
          )}
        </div>
        <div className={`text ${styles.text}`}>
          <h1 className={`hero-text-main ${styles.heroTextMain}`}>{associationName}</h1>
          {heroSubtitle ? <h3 className={`hero-text-sub ${styles.heroTextSub}`}>{heroSubtitle}</h3> : null}
        </div>
      </header>
    );
  }

  return (
    <header className={`${styles.header} header home-hero-legacy ${rootClassName}`}>
      <div className={`hero-text-box ${styles.heroTextBox}`}>
        <div
          className={
            isKkBrand
              ? `${styles.scalingSvgContainer} scaling-svg-container home-hero-logo-wrap ${styles.logoWrap}`
              : `${styles.albin} albin home-hero-logo-wrap ${styles.logoWrap}`
          }
        >
          {inlineHeroLogo ? (
            <div
              className={`home-hero-logo-inline home-hero-logo-inline--animated ${styles.logoInline}`}
              aria-hidden="true"
              dangerouslySetInnerHTML={{ __html: inlineHeroLogo }}
            />
          ) : (
            <img
              src={heroLogo}
              alt={associationName}
              className={`home-hero-logo home-hero-logo--animated ${styles.logo} ${styles.logoAnimated}`}
            />
          )}
        </div>
        <div className={`text ${styles.text}`}>
          <h1 className={styles.title}>{associationName}</h1>
          {heroSubtitle ? <h3 className={styles.subtitle}>{heroSubtitle}</h3> : null}
        </div>
      </div>
    </header>
  );
}
