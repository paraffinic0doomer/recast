/**
 * Whether this build lists the project library.
 *
 * The workspace is normally the point: Studio, Projects, Campaigns and Assets
 * all enumerate what has been uploaded. On a publicly reachable deployment
 * that turns the library into a directory of the owner's source videos, which
 * is not something a visitor should browse.
 *
 * Set NEXT_PUBLIC_HIDE_LIBRARY=true on the public build and the listing pages
 * stop enumerating. A project opened by its own URL still works, so a link can
 * be shared deliberately — the library is unlisted, not sealed.
 *
 * Read at build time, so the local build (flag unset) keeps the full library
 * while the hosted build hides it, from the same source.
 */
export const HIDE_LIBRARY = process.env.NEXT_PUBLIC_HIDE_LIBRARY === "true";
