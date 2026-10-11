import { expect, test } from "bun:test";
import { renderToStaticMarkup } from "react-dom/server";
import { Clock, SquareCheck, Triangle } from "./icons";

const paths = (html: string) =>
	[...html.matchAll(/ d="([^"]*)"/g)].map((m) => m[1]);

test("every curve and arc is straightened, with square caps and mitred joins", () => {
	const html = renderToStaticMarkup(<Triangle size={22} strokeWidth={2.25} />);
	expect(html).toContain('stroke-linecap="square"');
	expect(html).toContain('stroke-linejoin="miter"');
	expect(html).toContain('stroke-width="2.25"');
	for (const d of paths(html)) expect(d).toMatch(/^M[\d.\s-]+(L[\d.\s-]+)*Z?$/);
});

test("a circle becomes an octagon, a rounded square a square", () => {
	const clock = renderToStaticMarkup(<Clock />);
	const ring = paths(clock).find((d) => d.endsWith("Z"));
	expect(ring?.match(/[ML]/g)).toHaveLength(8);
	const box = renderToStaticMarkup(<SquareCheck />);
	expect(box).toContain("<rect");
	expect(box).not.toContain("rx=");
});
