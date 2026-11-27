const text = (value) => document.createTextNode(value);
const el = (tag, children = [], attrs = {}) => {
  const node = Object.assign(document.createElement(tag), attrs);
  node.append(...children);
  return node;
};
const link = (item) => el("a", [text(item.label)], { href: item.url });

fetch("days.json")
  .then((response) => response.json())
  .then((page) => {
    document.getElementById("title").textContent = page.title;
    document.getElementById("intro").textContent = page.intro;
    document.getElementById("stats").append(
      ...page.stats.map((s) => el("div", [el("b", [text(s.value)]), text(s.label)]))
    );
    document.getElementById("days").append(
      ...page.days.map((d) =>
        el(
          "article",
          [
            el("h2", [text(`Day ${d.day}, ${d.area} `), el("span", [text(d.status)], { className: "tag" })]),
            el("p", [text(d.finding)]),
            el("p", [el("b", [text("Shipped. ")]), text(d.shipped)]),
            ...(d.post ? [el("h3", [text("Post for X")]), el("pre", [text(d.post)], { className: "post" })] : []),
            ...(d.links ? [el("ul", d.links.map((l) => el("li", [link(l)])))] : []),
            ...[
              ["Tweet about the discovery", d.discoveryTweet],
              ["Tweet about the fix", d.fixTweet],
            ].map(([label, url]) =>
              el("p", url ? [link({ label, url })] : [text(`${label}, coming soon`)])
            ),
          ],
          { className: d.status }
        )
      )
    );
    document.getElementById("data").append(...page.data.map((l) => el("li", [link(l)])));
  });
