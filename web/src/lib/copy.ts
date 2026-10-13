import { useEffect, useState } from "react";

const COPIED_MS = 1500; // how long the button says what happened

// A copy button for `text`: what it says for a moment after a click, « Copied » or « Copy
// failed », and the click. The clipboard API is missing outside a secure context: inside
// the promise, its absence is a rejection like any other.
export function useCopy(text: string): [string, () => void] {
	const [said, setSaid] = useState("");
	useEffect(() => {
		if (!said) return;
		const t = setTimeout(() => setSaid(""), COPIED_MS);
		return () => clearTimeout(t);
	}, [said]);
	const copy = () =>
		Promise.resolve()
			.then(() => navigator.clipboard.writeText(text))
			.then(
				() => setSaid("Copied"),
				() => setSaid("Copy failed"),
			);
	return [said, copy];
}
