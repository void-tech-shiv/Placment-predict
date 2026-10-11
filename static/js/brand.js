document.addEventListener('DOMContentLoaded', () => {
  const replacements = [
    [/PlacementAI/g, 'Placement Predict'],
    [/Placement Prediction System/g, 'Placement Predict']
  ];

  const replaceText = (value) => {
    let next = value;
    replacements.forEach(([pattern, replacement]) => {
      next = next.replace(pattern, replacement);
    });
    return next;
  };

  document.title = replaceText(document.title);

  const walker = document.createTreeWalker(
    document.body,
    NodeFilter.SHOW_TEXT,
    {
      acceptNode(node) {
        const parent = node.parentElement;
        if (!parent || ['SCRIPT', 'STYLE', 'TEXTAREA'].includes(parent.tagName)) {
          return NodeFilter.FILTER_REJECT;
        }
        return replacements.some(([pattern]) => {
          pattern.lastIndex = 0;
          return pattern.test(node.nodeValue || '');
        }) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
      }
    }
  );

  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  nodes.forEach((node) => {
    node.nodeValue = replaceText(node.nodeValue || '');
  });
});
