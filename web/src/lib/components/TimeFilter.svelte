<script lang="ts">
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu/index.js';
	import { Button } from '$lib/components/ui/button/index.js';
	import { RangeCalendar } from '$lib/components/ui/range-calendar/index.js';

	import {
		CalendarDate,
		DateFormatter,
		type DateValue,
		getLocalTimeZone
	} from '@internationalized/date';

	let now = +new Date();

	const rangeMap = {
		unlimited: {
			label: '不限时间',
			start: null,
			end: null
		},
		today: {
			label: '今天',
			start: now - 24 * 60 * 60 * 1000,
			end: now
		},
		week: {
			label: '最近一周',
			start: now - 7 * 24 * 60 * 60 * 1000,
			end: now
		},
		month: {
			label: '最近一个月',
			start: now - 30 * 24 * 60 * 60 * 1000,
			end: now
		},
		threeMonths: {
			label: '最近三个月',
			start: now - 90 * 24 * 60 * 60 * 1000,
			end: now
		},
		custom: {
			label: '自定义',
			start: null,
			end: null
		}
	};

	let timeFilter = 'unlimited';
	export let start: number;
	export let end: number;

	let customDateRange = {
		start: null,
		end: null
	};

	function updateCustomDateRange(range: { start: DateValue | null; end: DateValue | null }) {
		if (range.start && range.end) {
            rangeMap.custom.start = range.start.toDate(getLocalTimeZone()).getTime();
            rangeMap.custom.end = range.end.toDate(getLocalTimeZone()).getTime();
			if (timeFilter !== 'custom') {
				timeFilter = 'custom';
			}
		}
	}

	$: updateCustomDateRange(customDateRange);

	$: if (timeFilter !== 'custom') {
		customDateRange = {
			start: null,
			end: null
		};
	}

	$: displayText =
		(timeFilter === 'custom' && customDateRange.start && customDateRange.end)
			? `${customDateRange.start?.toString()} - ${customDateRange.end?.toString()}`
			: rangeMap[timeFilter].label;
	$: start = rangeMap[timeFilter].start;
	$: end = rangeMap[timeFilter].end;
</script>

<div>
	<DropdownMenu.Root>
		<DropdownMenu.Trigger asChild let:builder>
			<Button
				variant="outline"
				size="sm"
				class="border p-2 text-xs font-medium focus:outline-none"
				builders={[builder]}
			>
				<span class="truncate">{displayText}</span>
			</Button>
		</DropdownMenu.Trigger>
		<DropdownMenu.Content class="w-56">
			<DropdownMenu.Label>时间筛选</DropdownMenu.Label>
			<DropdownMenu.Separator />
			<DropdownMenu.RadioGroup bind:value={timeFilter}>
				<DropdownMenu.RadioItem value="unlimited">时间不限</DropdownMenu.RadioItem>
				<DropdownMenu.RadioItem value="today">今天</DropdownMenu.RadioItem>
				<DropdownMenu.RadioItem value="week">最近一周</DropdownMenu.RadioItem>
				<DropdownMenu.RadioItem value="month">最近一个月</DropdownMenu.RadioItem>
				<DropdownMenu.RadioItem value="threeMonths">最近三个月</DropdownMenu.RadioItem>
				<DropdownMenu.Sub>
					<DropdownMenu.SubTrigger>自定义</DropdownMenu.SubTrigger>
					<DropdownMenu.SubContent>
						<RangeCalendar bind:value={customDateRange} />
					</DropdownMenu.SubContent>
				</DropdownMenu.Sub>
			</DropdownMenu.RadioGroup>
		</DropdownMenu.Content>
	</DropdownMenu.Root>
</div>