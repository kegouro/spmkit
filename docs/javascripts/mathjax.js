window.MathJax = {
  tex: {
    inlineMath: [["\\(", "\\)"]],
    displayMath: [["\\[", "\\]"]],
    processEscapes: true,
    processEnvironments: true,
  },
  options: {
    ignoreHtmlClass: ".*|",
    processHtmlClass: "arithmatex",
  },
};

const mathJaxLoader = document.currentScript;
let mathJaxPromise;

function renderMath() {
  if (!document.querySelector(".arithmatex")) return;
  if (typeof window.MathJax.typesetPromise === "function") {
    window.MathJax.typesetPromise();
    return;
  }
  if (!mathJaxPromise) {
    mathJaxPromise = new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = new URL(
        "../assets/vendor/mathjax/tex-mml-chtml.js",
        mathJaxLoader.src,
      ).href;
      script.defer = true;
      script.addEventListener("load", resolve, { once: true });
      script.addEventListener("error", reject, { once: true });
      document.head.appendChild(script);
    });
  }
  mathJaxPromise.then(() => window.MathJax.typesetPromise());
}

if (typeof document$ !== "undefined") document$.subscribe(renderMath);
else document.addEventListener("DOMContentLoaded", renderMath, { once: true });
