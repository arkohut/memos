<script lang="ts">
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu/index.js';
	import { Button } from '$lib/components/ui/button/index.js';
	import { RangeCalendar } from '$lib/components/ui/range-calendar/index.js';
	import { _ } from 'svelte-i18n';

	import {
		type DateValue,
		getLocalTimeZone
	} from '@internationalized/date';

	let now = +new Date();

	let rangeMap: {
		[key: string]: {
			label: string;
			start: number | null;
			end: number | null;
		};
	};

	$: rangeMap = {
		unlimited: {
			label: $_('timeFilter.unlimited'),
			start: null,
			end: null
		},
		threeHours: {
			label: $_('timeFilter.threeHours'),
			start: now - 3 * 60 * 60 * 1000,
			end: now
		},
		today: {
			label: $_('timeFilter.today'),
			start: now - 24 * 60 * 60 * 1000,
			end: now
		},
		week: {
			label: $_('timeFilter.week'),
			start: now - 7 * 24 * 60 * 60 * 1000,
			end: now
		},
		month: {
			label: $_('timeFilter.month'),
			start: now - 30 * 24 * 60 * 60 * 1000,
			end: now
		},
		threeMonths: {
			label: $_('timeFilter.threeMonths'),
			start: now - 90 * 24 * 60 * 60 * 1000,
			end: now
		},
		custom: {
			label: $_('timeFilter.custom'),
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
			? $_('timeFilter.customRange', { values: { start: customDateRange.start?.toString(), end: customDateRange.end?.toString() } })
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
		<DropdownMenu.Content class="w-56" align="start" side="bottom">
			<DropdownMenu.Label>{$_('timeFilter.label')}</DropdownMenu.Label>
			<DropdownMenu.Separator />
			<DropdownMenu.RadioGroup bind:value={timeFilter}>
				<DropdownMenu.RadioItem value="unlimited">{$_('timeFilter.unlimited')}</DropdownMenu.RadioItem>
				<DropdownMenu.RadioItem value="threeHours">{$_('timeFilter.threeHours')}</DropdownMenu.RadioItem>
				<DropdownMenu.RadioItem value="today">{$_('timeFilter.today')}</DropdownMenu.RadioItem>
				<DropdownMenu.RadioItem value="week">{$_('timeFilter.week')}</DropdownMenu.RadioItem>
				<DropdownMenu.RadioItem value="month">{$_('timeFilter.month')}</DropdownMenu.RadioItem>
				<DropdownMenu.RadioItem value="threeMonths">{$_('timeFilter.threeMonths')}</DropdownMenu.RadioItem>
				<DropdownMenu.Sub>
					<DropdownMenu.SubTrigger>{$_('timeFilter.custom')}</DropdownMenu.SubTrigger>
					<DropdownMenu.SubContent>
						<RangeCalendar bind:value={customDateRange} />
					</DropdownMenu.SubContent>
				</DropdownMenu.Sub>
			</DropdownMenu.RadioGroup>
		</DropdownMenu.Content>
	</DropdownMenu.Root>
</div>
