import { useEffect, useRef, useState } from "react";
import { continueRender, delayRender } from "remotion";

/**
 * Hold the frame until a CSS backdrop image has actually decoded.
 *
 * WHY THIS EXISTS
 * ---------------
 * Remotion's `<Img>` holds a frame open until its image loads. A CSS
 * `backgroundImage: url(...)` does not: the frame is captured whenever the
 * renderer is ready, and if the bitmap has not arrived the backdrop is simply
 * missing from it.
 *
 * Measured on king-tut's c006, a title sequence whose backdrop is a JPEG,
 * rendering frames 1384-1560 twice from the same props on the same machine:
 *
 *     concurrency 4   all 177 frames match the full render, max 0.2555
 *     concurrency 1   1385 wrong by 2.518, 1386 by 4.226, 1387 by 5.428
 *
 * and across three further renders of the same range the frame that lost the
 * race was a different one each time — frame 3, then 4, then 6. It is a race,
 * so a full render can lose it too; it simply had not yet, which is the worst
 * way for a defect to be stable.
 *
 * `delayRender` is the mechanism `<Img>` itself uses. An image that fails to
 * load continues the render rather than hanging it: a missing backdrop is a
 * bad frame, and a render that never finishes is a lost night.
 */
export const useBackdrop = (src?: string): void => {
  const [handle] = useState(() =>
    src ? delayRender(`backdrop ${src}`) : null);
  const done = useRef(false);

  useEffect(() => {
    if (handle === null || done.current) return;
    const finish = () => {
      if (done.current) return;
      done.current = true;
      continueRender(handle);
    };
    const image = new Image();
    image.onload = finish;
    image.onerror = finish;
    image.src = src as string;
    if (image.complete) finish();
    return () => finish();
  }, [src, handle]);
};
