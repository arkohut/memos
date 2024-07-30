<script lang="ts">
    import { Calendar } from "lucide-svelte";
    import type { DateRange } from "bits-ui";
    import {
      CalendarDate,
      DateFormatter,
      type DateValue,
      getLocalTimeZone
    } from "@internationalized/date";
    import { cn } from "$lib/utils.js";
    import { Button } from "$lib/components/ui/button/index.js";
    import { RangeCalendar } from "$lib/components/ui/range-calendar/index.js";
    import * as Popover from "$lib/components/ui/popover/index.js";
    import { onMount } from "svelte";

    const df = new DateFormatter("en-US", {
      dateStyle: "medium"
    });

    export let startTimestamp: number;
    export let endTimestamp: number;
   
    let value: DateRange | undefined;
    let initialized = false; // Flag to control reactive updates
    let userSelected = false; // New flag to track user selection
    
    onMount(() => {
      const now = new Date();
      const year = now.getFullYear();
      const month = now.getMonth() + 1; // getMonth() returns 0-11
      const date = now.getDate();
      value = {
        start: new CalendarDate(year, month, date).subtract({ days: 30 }),
        end: new CalendarDate(year, month, date)
      };
      console.log(initialized);
      initialized = true;
    });

    $: if (initialized && value && value.start && value.end && !userSelected) {
      userSelected = true; // Set flag when user selects a range
      startTimestamp = value.start.toDate(getLocalTimeZone()).getTime() / 1000;
      endTimestamp = value.end.toDate(getLocalTimeZone()).getTime() / 1000;
    }
    
    let startValue: DateValue | undefined = undefined;
  </script>
   
  <div class="grid gap-2">
    <Popover.Root openFocus>
      <Popover.Trigger asChild let:builder>
        <Button
          variant="outline"
          class={cn(
            "w-[220px] justify-start text-center font-normal text-xs",
            (startTimestamp === -1 && endTimestamp === -1) && "text-muted-foreground"
          )}
          builders={[builder]}
        >
          <Calendar class="mr-2 h-4 w-4" />
          {#if startTimestamp === -1 && endTimestamp === -1}
            不限时间
          {:else if value && value.start}
            {#if value.end}
              {df.format(value.start.toDate(getLocalTimeZone()))} - {df.format(
                value.end.toDate(getLocalTimeZone())
              )}
            {:else}
              {df.format(value.start.toDate(getLocalTimeZone()))}
            {/if}
          {:else if startValue}
            {df.format(startValue.toDate(getLocalTimeZone()))}
          {:else}
            Pick a date
          {/if}
        </Button>
      </Popover.Trigger>
      <Popover.Content class="w-auto p-0" align="start">
        <RangeCalendar
          bind:value
          bind:startValue
          initialFocus
          numberOfMonths={2}
          placeholder={value?.start}
        />
      </Popover.Content>
    </Popover.Root>
  </div>