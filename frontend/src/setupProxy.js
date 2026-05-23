// CRA dev-server middleware: send no-cache headers on every response so
// Safari iPad can't pin an old bundle.js across previews.
//
// Without this, the preview URL fetched outside the Emergent iframe (e.g.
// pasted into Safari's address bar) gets cached aggressively and users
// can keep hitting bugs that were already fixed.

module.exports = function (app) {
  app.use((req, res, next) => {
    res.setHeader(
      "Cache-Control",
      "no-store, no-cache, must-revalidate, proxy-revalidate"
    );
    res.setHeader("Pragma", "no-cache");
    res.setHeader("Expires", "0");
    res.setHeader("Surrogate-Control", "no-store");
    next();
  });
};
