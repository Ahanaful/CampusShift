import js from "@eslint/js";
import globals from "globals";

export default [
  {
    files: ["src/**/*.{js,jsx}"],
    languageOptions: {
      ecmaVersion: "latest",
      sourceType: "module",
      globals: globals.browser,
      parserOptions: { ecmaFeatures: { jsx: true } },
    },
    rules: {
      ...js.configs.recommended.rules,
      "no-unused-vars": [
        "error",
        {
          varsIgnorePattern: "^[A-Z]",
          argsIgnorePattern: "^_",
          ignoreRestSiblings: true,
        },
      ],
    },
  },
];
