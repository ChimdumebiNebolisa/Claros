import type { Preview } from "@storybook/react";
import "../src/styles/tailwind.css";
import "../src/styles/tokens.css";
import "../src/styles/app.css";

const preview: Preview = {
  parameters: {
    a11y: { test: "todo" },
    controls: { matchers: { color: /(background|color)$/i, date: /Date$/i } },
  },
};

export default preview;
