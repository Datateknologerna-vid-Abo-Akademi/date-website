"use client";

import { useEffect, useState } from "react";

export function HomeJoke() {
  const [joke, setJoke] = useState("");
  const [showHeading, setShowHeading] = useState(true);

  useEffect(() => {
    let isMounted = true;

    async function fetchJoke() {
      try {
        const response = await fetch("https://icanhazdadjoke.com", {
          headers: { Accept: "application/json" },
        });
        if (!response.ok) {
          if (isMounted) {
            setShowHeading(false);
          }
          return;
        }
        const payload = (await response.json()) as { joke?: string };
        if (isMounted) {
          setJoke(payload.joke ?? "");
        }
      } catch {
        if (isMounted) {
          setShowHeading(false);
        }
      }
    }

    fetchJoke().catch(() => undefined);
    return () => {
      isMounted = false;
    };
  }, []);

  return (
    <>
      {showHeading ? <h5>Joke</h5> : null}
      <p>{joke}</p>
    </>
  );
}
