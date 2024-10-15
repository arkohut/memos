import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";
import { cubicOut } from "svelte/easing";
import type { TransitionConfig } from "svelte/transition";

export function cn(...inputs: ClassValue[]) {
	return twMerge(clsx(inputs));
}

type FlyAndScaleParams = {
	y?: number;
	x?: number;
	start?: number;
	duration?: number;
};

export const flyAndScale = (
	node: Element,
	params: FlyAndScaleParams = { y: -8, x: 0, start: 0.95, duration: 150 }
): TransitionConfig => {
	const style = getComputedStyle(node);
	const transform = style.transform === "none" ? "" : style.transform;

	const scaleConversion = (
		valueA: number,
		scaleA: [number, number],
		scaleB: [number, number]
	) => {
		const [minA, maxA] = scaleA;
		const [minB, maxB] = scaleB;

		const percentage = (valueA - minA) / (maxA - minA);
		const valueB = percentage * (maxB - minB) + minB;

		return valueB;
	};

	const styleToString = (
		style: Record<string, number | string | undefined>
	): string => {
		return Object.keys(style).reduce((str, key) => {
			if (style[key] === undefined) return str;
			return str + `${key}:${style[key]};`;
		}, "");
	};

	return {
		duration: params.duration ?? 200,
		delay: 0,
		css: (t) => {
			const y = scaleConversion(t, [0, 1], [params.y ?? 5, 0]);
			const x = scaleConversion(t, [0, 1], [params.x ?? 0, 0]);
			const scale = scaleConversion(t, [0, 1], [params.start ?? 0.95, 1]);

			return styleToString({
				transform: `${transform} translate3d(${x}px, ${y}px, 0) scale(${scale})`,
				opacity: t
			});
		},
		easing: cubicOut
	};
};

export const appIconMap: Record<string, string> = {
	"Cursor": "Code",
	"Google Chrome": "Chrome",
	"IINA": "Youtube",
	"微信": "MessageSquareCode",
	"预览": "Eye",
	"iTerm2": "SquareTerminal",
	"企业微信": "MessageSquareCode",
	"IntelliJ IDEA": "Code",
	"Microsoft Edge": "Globe",
	"腾讯会议": "MessagesSquare",
	"访达": "Folder",
	"邮件": "Mail",
	"备忘录": "NotebookTabs",
	"日历": "CalendarFold",
	"UserNotificationCenter": "Bell",
	"Electron": "Atom",
	"Firefox": "Globe",
	"Safari浏览器": "Compass",
	"熊掌记": "NotebookTabs",
	"Alacritty": "SquareTerminal",
	"系统设置": "Settings",
	"股市": "CircleDollarSign",
	"活动监视器": "Activity",
	"Brave Browser": "Globe",
	"Code": "Code",
};
