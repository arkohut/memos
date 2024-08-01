<script lang="ts">
	import { onMount } from 'svelte';

	import { Button } from '$lib/components/ui/button/index.js';
	import { Checkbox } from '$lib/components/ui/checkbox/index.js';
	import { Label } from '$lib/components/ui/label/index.js';
	import * as Popover from '$lib/components/ui/popover/index.js';
	import { Separator } from '$lib/components/ui/separator/index.js';
	import { PUBLIC_API_ENDPOINT } from '$env/static/public';

	const apiEndpoint =
		typeof PUBLIC_API_ENDPOINT !== 'undefined' ? PUBLIC_API_ENDPOINT : window.location.origin;

	async function fetchLibraries() {
		try {
			const response = await fetch(`${apiEndpoint}/libraries`);
			if (!response.ok) {
				throw new Error('Failed to fetch libraries');
			}
			const libraries = await response.json();
			return libraries;
		} catch (error) {
			console.error('Error fetching libraries:', error);
			return [];
		}
	}

	export let selectedLibraryIds: number[] = [];

	let popoverOpen = false;

	let libraries: { id: number; name: string }[] = [];
	let selectedLibraries: Record<number, boolean> = {};
	let allSelected = true;

	let displayName = '全部';

	let prevSelectedLibraryIds: number[] = [];

	async function toggleSelectAll(checked: boolean) {
		allSelected = checked;
		
		if (checked) {
			popoverOpen = false;
			selectedLibraries = {};
			selectedLibraryIds = [];
			prevSelectedLibraryIds = [];
		}
	}

	$: {
		const selectedCount = Object.values(selectedLibraries).filter(Boolean).length;
		let newSelectedLibraryIds: number[] = [];

		if (selectedCount > 0 && selectedCount < libraries.length) {
			allSelected = false;
			newSelectedLibraryIds = Object.entries(selectedLibraries)
				.filter(([_, isSelected]) => isSelected)
				.map(([id, _]) => +id);
			displayName = newSelectedLibraryIds
				.map((id) => libraries.find(lib => lib.id === id)?.name)
				.join(', ');
		} else if (selectedCount === 0) {
			displayName = '全部';
			allSelected = true;
			selectedLibraries = {};
			newSelectedLibraryIds = [];
		} else {
			displayName = '全部';
			allSelected = true;
			selectedLibraries = {};
			newSelectedLibraryIds = [];
			popoverOpen = false;
		}

		// 只在值真正改变时才更新 selectedLibraryIds
		if (JSON.stringify(newSelectedLibraryIds) !== JSON.stringify(prevSelectedLibraryIds)) {
			selectedLibraryIds = newSelectedLibraryIds;
			prevSelectedLibraryIds = newSelectedLibraryIds;
		}
	}

	// Fetch libraries when the component is mounted

	onMount(async () => {
		libraries = await fetchLibraries();
	});
</script>

<div>
	<Popover.Root portal={null} bind:open={popoverOpen}>
		<Popover.Trigger>
			<Button
				class="border p-2 text-xs font-medium focus:outline-none"
				size="sm"
				variant="outline">{displayName}</Button
			>
		</Popover.Trigger>
		<Popover.Content class="w-56 mt-1 p-1" align="start" side="bottom">
			<div class="px-2 py-1.5 text-sm font-semibold">
				<Label class="text-sm font-semibold">仓库筛选</Label>
			</div>
			<Separator class="my-1" />
			<div class="px-2 py-1.5">
				<div class="mb-2 items-top flex space-x-2">
					<Checkbox id="all-selected" bind:checked={allSelected} disabled={allSelected} onCheckedChange={toggleSelectAll} />
					<Label for="all-selected" class="flex items-center text-sm">全选</Label>
				</div>
				{#each libraries as library}
					<div class="mb-2 items-top flex space-x-2">
						<Checkbox
							id={`library-${library.id}`}
							bind:checked={selectedLibraries[library.id]}
						/>
						<Label for={`library-${library.id}`} class="flex items-center text-sm">{library.name}</Label>
					</div>
				{/each}
			</div>
		</Popover.Content>
	</Popover.Root>
</div>