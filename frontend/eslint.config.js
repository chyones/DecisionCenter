import js from '@eslint/js';
import globals from 'globals';
import tseslint from 'typescript-eslint';

// Phase 1I bootstrap lint config. React-hooks / react-refresh plugins are added
// in the components slice; this slice keeps lint minimal and green.
export default tseslint.config(
  { ignores: ['dist', 'scripts'] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ['**/*.{ts,tsx}'],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: 'module',
      globals: { ...globals.browser, ...globals.node },
    },
  },
);
