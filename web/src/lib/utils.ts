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

export function translateAppName(appName: string): string | undefined {
	// Remove the '.exe' suffix for Windows app names
	const cleanedAppName = appName.replace(/\.exe$/, '');

	const appIconMap: Record<string, string> = {
		"chrome": "Chrome",
		"firefox": "Globe",
		"edge": "Globe",
		"msedge": "Globe",
		"code": "Code",
		"cursor": "Code",

		"windows app beta": "LayoutGrid",
		"windows app preview": "LayoutGrid",
		
		"google chrome": "Chrome",
		"iina": "Youtube",
		"微信": "MessageSquareCode",
		"预览": "Eye",
		"iterm2": "SquareTerminal",
		"企业微信": "MessageSquareCode",
		"intellij idea": "Code",
		"microsoft edge": "Globe",
		"腾讯会议": "Phone",
		"访达": "Folder",
		"邮件": "Mail",
		"备忘录": "NotebookTabs",
		"日历": "CalendarFold",
		"usernotificationcenter": "Bell",
		"electron": "Atom",
		"safari浏览器": "Compass",
		"熊掌记": "NotebookTabs",
		"alacritty": "SquareTerminal",
		"系统设置": "Settings",
		"股市": "CircleDollarSign",
		"活动监视器": "Activity",
		"brave browser": "Globe",

		"windowsterminal": "SquareTerminal",
		"explorer": "Folder",
		"clash for windows": "Globe",
		"mpv": "Youtube",
		"searchhost": "Search",
		"lockapp": "Lock",
		"thunder": "CloudDownload",
		"xlliveud": "CloudDownload",
		"ollama app": "Bot",
		"githubdesktop": "Github",
	};

	// Try to match the cleaned app name (case-insensitive)
	const iconName = appIconMap[cleanedAppName.toLowerCase()];
	
	// If no match is found, return undefined
	return iconName;
}
