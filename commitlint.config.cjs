module.exports = {
  extends: ["@commitlint/config-conventional"],
  rules: {
    // "body-max-line-length" stays disabled via severity 0; keep the tuple to document
    // the intended limit if the rule is re-enabled later.
    "body-max-line-length": [0, "always", 100],
  },
};
