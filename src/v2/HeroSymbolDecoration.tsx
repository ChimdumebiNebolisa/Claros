import "./hero-symbol-decoration.css";

const symbols = [
  { glyph: "x²", kind: "math", position: "one" },
  { glyph: "π", kind: "math", position: "two" },
  { glyph: "√", kind: "math", position: "three" },
  { glyph: "¾", kind: "fraction", position: "four" },
  { glyph: "÷", kind: "math", position: "five" },
  { glyph: "Aa", kind: "letters", position: "six" },
  { glyph: "“ ”", kind: "quote", position: "seven" },
  { glyph: "¶", kind: "letters", position: "eight" },
  { glyph: "?", kind: "punctuation", position: "nine" },
  { glyph: "∑", kind: "math", position: "ten" },
  { glyph: "½", kind: "fraction", position: "eleven" },
  { glyph: "…", kind: "punctuation", position: "twelve" },
  { glyph: "∠", kind: "math", position: "thirteen" },
  { glyph: "!", kind: "punctuation", position: "fourteen" },
  { glyph: "≠", kind: "math", position: "fifteen" },
  { glyph: "()", kind: "letters", position: "sixteen" },
  { glyph: "∴", kind: "math", position: "seventeen" },
  { glyph: ":", kind: "punctuation", position: "eighteen" },
  { glyph: "∞", kind: "math", position: "nineteen" },
  { glyph: "×", kind: "math", position: "twenty" },
  { glyph: "%", kind: "punctuation", position: "twenty-one" },
  { glyph: "∫", kind: "math", position: "twenty-two" },
  { glyph: "=", kind: "math", position: "twenty-three" },
  { glyph: "∆", kind: "math", position: "twenty-four" },
  { glyph: "∼", kind: "math", position: "twenty-five" },
] as const;

export default function HeroSymbolDecoration() {
  return (
    <div className="claros-hero-symbols" aria-hidden="true">
      {symbols.map(({ glyph, kind, position }) => (
        <span
          key={position}
          className={`claros-hero-symbol claros-hero-symbol--${kind} claros-hero-symbol--${position}`}
        >
          {glyph}
        </span>
      ))}
    </div>
  );
}
