import { useSyncExternalStore } from "react";

// Values by key that outlive the view, which unmounts on every switch: a replay takes up
// to a minute and a « Pourquoi ? » answer several seconds, so neither may be lost or rerun.
export class Keyed<T> {
	private values = new Map<string, T>();
	private listeners = new Set<() => void>();

	subscribe = (listener: () => void) => {
		this.listeners.add(listener);
		return () => {
			this.listeners.delete(listener);
		};
	};

	get(key: string) {
		return this.values.get(key);
	}

	set(key: string, value: T) {
		this.values.set(key, value);
		for (const listener of this.listeners) listener();
	}
}

export const useKeyed = <T>(store: Keyed<T>, key: string) =>
	useSyncExternalStore(store.subscribe, () => store.get(key));
