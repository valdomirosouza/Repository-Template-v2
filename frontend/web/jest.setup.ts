// Loaded after the test framework (jest.config.ts → setupFilesAfterEnv). The side-effect
// import registers @testing-library/jest-dom's custom matchers (toBeInTheDocument, etc.)
// at runtime and augments the global `expect` types for TypeScript.
import "@testing-library/jest-dom";
