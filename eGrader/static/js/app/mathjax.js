import _ from 'underscore'

var COMBINED_MATH_SELECTOR, MATH_DATA_SELECTOR, MATH_MARKER_BLOCK,
    MATH_MARKER_INLINE, MATH_ML_SELECTOR, MATH_RENDERED_CLASS, 
    setAsRendered, startMathJax, typesetDocument, typesetMath;

MATH_MARKER_BLOCK = '\u200c\u200c\u200c';

MATH_MARKER_INLINE = '\u200b\u200b\u200b';

MATH_RENDERED_CLASS = 'math-rendered';

MATH_DATA_SELECTOR = "[data-math]:not(." + MATH_RENDERED_CLASS + ")";

MATH_ML_SELECTOR = "math:not(." + MATH_RENDERED_CLASS + ")";

COMBINED_MATH_SELECTOR = MATH_DATA_SELECTOR + ", " + MATH_ML_SELECTOR;

setAsRendered = function(node, type) {
  if (type == null) {
    type = 'mathjax';
  }
  node.classList.add(type + "-rendered");
  return node.classList.add(MATH_RENDERED_CLASS);
};

typesetDocument = function() {
  var allNodes, formula, i, len, node, ref;
  allNodes = [];
  ref = document.querySelectorAll(MATH_DATA_SELECTOR);
    // console.log(ref);
  for (i = 0, len = ref.length; i < len; i++) {
    node = ref[i];
    formula = node.getAttribute('data-math');
    if (node.tagName.toLowerCase() === 'div') {
      node.textContent = "" + MATH_MARKER_BLOCK + formula + MATH_MARKER_BLOCK;
    } else {
      node.textContent = "" + MATH_MARKER_INLINE + formula + MATH_MARKER_INLINE;
    }
    allNodes.push(node);
  }
  allNodes = allNodes.concat(_.pluck(document.querySelectorAll(MATH_ML_SELECTOR), 'parentNode'));
  window.MathJax.Hub.Typeset(allNodes);
  return window.MathJax.Hub.Queue(function() {
    var j, len1, results;
    results = [];
    for (j = 0, len1 = allNodes.length; j < len1; j++) {
      node = allNodes[j];
      results.push(setAsRendered(node));
    }
    return results;
  });
};

typesetDocument = _.debounce(typesetDocument, 10);

typesetMath = function(root) {
  var ref, ref1;
  // console.log(root.querySelector(COMBINED_MATH_SELECTOR));
  if ((((ref = window.MathJax) != null ? (ref1 = ref.Hub) != null ? ref1.Queue : void 0 : void 0) != null) && root.querySelector(COMBINED_MATH_SELECTOR)) {
      return typesetDocument();
  }
};

startMathJax = function(callback) {
  var MATHJAX_CONFIG, configuredCallback, ref;
  MATHJAX_CONFIG = {
    showProcessingMessages: false,
    tex2jax: {
      displayMath: [[MATH_MARKER_BLOCK, MATH_MARKER_BLOCK]],
      inlineMath: [[MATH_MARKER_INLINE, MATH_MARKER_INLINE]]
    },
    styles: {
      '#MathJax_Message': {
        visibility: 'hidden',
        left: '',
        right: 0
      },
      '#MathJax_MSIE_Frame': {
        visibility: 'hidden',
        left: '',
        right: 0
      }
    }
  };
  configuredCallback = function() {
    return window.MathJax.Hub.Configured();
  };
  if ((ref = window.MathJax) != null ? ref.Hub : void 0) {
    window.MathJax.Hub.Config(MATHJAX_CONFIG);
    window.MathJax.Hub.processSectionDelay = 0;
    return configuredCallback();
  } else {
    MATHJAX_CONFIG.AuthorInit = configuredCallback;
    return window.MathJax = MATHJAX_CONFIG;
  }

  if (typeof(callback) == 'function') {
    callback()
  }

};

export {startMathJax, typesetMath}
