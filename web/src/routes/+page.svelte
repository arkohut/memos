<script lang="ts">
	import { onMount } from 'svelte';
	import Figure from '$lib/Figure.svelte';
	import TimeFilter from '$lib/components/TimeFilter.svelte';
	import LibraryFilter from '$lib/components/LibraryFilter.svelte';
	import { Input } from '$lib/components/ui/input';
	import { PUBLIC_API_ENDPOINT } from '$env/static/public';
	import FacetFilter from '$lib/components/FacetFilter.svelte';
	import { formatDistanceToNow } from 'date-fns';

	let searchString = '';
	/**
	 * @type {any[]}
	 */
	let searchResults = [];
	let isLoading = false;
	let debounceTimer: ReturnType<typeof setTimeout>;
	let showModal = false;
	let selectedImage = 0;

	let startTimestamp = -1;
	let endTimestamp = -1;

	let selectedLibraries: number[] = [];
	let searchResult: SearchResult | null = null;

	interface FacetCount {
		value: string;
		count: number;
	}

	interface Facet {
		field_name: string;
		counts: FacetCount[];
	}

	interface SearchResult {
		hits: any[];
		facet_counts: Facet[];
		found: number;
		out_of: number;
		search_time_ms: number;
	}

	let selectedTags: Record<string, boolean> = {};
	let selectedDates: Record<string, boolean> = {};

	const debounceDelay = 300;
	const apiEndpoint =
		typeof PUBLIC_API_ENDPOINT !== 'undefined' ? PUBLIC_API_ENDPOINT : window.location.origin;

	let facetCounts: Facet[] | null = null;

	async function searchItems(
		query: string,
		start: number,
		end: number,
		selectedLibraries: number[],
		selectedTags: string[],
		selectedDates: string[],
		updateFacets: boolean = false
	) {
		isLoading = true;

		try {
			let url = `${apiEndpoint}/search?q=${encodeURIComponent(query)}`;
			if (start > 0) {
				url += `&start=${Math.floor(start / 1000)}`;
			}
			if (end > 0) {
				url += `&end=${Math.floor(end / 1000)}`;
			}
			if (selectedLibraries.length > 0) {
				url += `&library_ids=${selectedLibraries.join(',')}`;
			}
			if (selectedTags.length > 0) {
				url += `&tags=${selectedTags.join(',')}`;
			}
			if (selectedDates.length > 0) {
				url += `&created_dates=${selectedDates.join(',')}`;
			}
			const response = await fetch(url);
			if (!response.ok) {
				throw new Error('Network response was not ok');
			}
			const result = await response.json();
			if (updateFacets) {
				facetCounts = result.facet_counts;
				selectedTags = Object.fromEntries(
					result.facet_counts
						.find((f) => f.field_name === 'tags')
						?.counts.map((t) => [t.value, false]) || []
				);
				selectedDates = Object.fromEntries(
					result.facet_counts
						.find((f) => f.field_name === 'created_date')
						?.counts.map((d) => [d.value, false]) || []
				);
			}
			searchResult = {
				...result,
				facet_counts: updateFacets ? result.facet_counts : facetCounts
				// Add other properties as needed
			};
			console.log(searchResult);
		} catch (error) {
			console.error('Search error:', error);
		} finally {
			isLoading = false;
		}
	}

	function handleSearchStringChange() {
		if (searchString.trim()) {
			debounceSearch(
				searchString,
				startTimestamp,
				endTimestamp,
				selectedLibraries,
				Object.keys(selectedTags).filter((tag) => selectedTags[tag]),
				Object.keys(selectedDates).filter((date) => selectedDates[date]),
				true // 更新 facets
			);
		} else {
			searchResults = [];
			searchResult = null;
			facetCounts = null;
		}
	}

	function handleFiltersChange() {
		if (searchString.trim()) {
			debounceSearch(
				searchString,
				startTimestamp,
				endTimestamp,
				selectedLibraries,
				Object.keys(selectedTags).filter((tag) => selectedTags[tag]),
				Object.keys(selectedDates).filter((date) => selectedDates[date]),
				false // 不更新 facets
			);
		}
	}

	$: {
		if (searchString.trim()) {
			handleSearchStringChange();
		} else {
			searchResults = [];
			searchResult = null;
			facetCounts = null;
		}
	}

	$: {
		if (startTimestamp !== -1 || endTimestamp !== -1 || selectedLibraries.length > 0) {
			handleFiltersChange();
		}
	}

	function handleTagChange(tag: string, checked: boolean) {
		selectedTags[tag] = checked;
		handleFiltersChange();
	}

	function handleDateChange(date: string, checked: boolean) {
		selectedDates[date] = checked;
		handleFiltersChange();
	}

	/**
	 * @param {string} query
	 * @param {number} start
	 * @param {number} end
	 * @param {number[]} selectedLibraries
	 * @param {string[]} selectedTags
	 * @param {string[]} selectedDates
	 * @param {boolean} updateFacets
	 */
	function debounceSearch(
		query: string,
		start: number,
		end: number,
		selectedLibraries: number[],
		selectedTags: string[],
		selectedDates: string[],
		updateFacets: boolean = true
	) {
		clearTimeout(debounceTimer);
		debounceTimer = setTimeout(() => {
			searchItems(query, start, end, selectedLibraries, selectedTags, selectedDates, updateFacets);
		}, debounceDelay);
	}

	/**
	 * @param {string} path
	 */
	function filename(path: string): string {
		let splits = path.split('/');
		return splits[splits.length - 1];
	}

	/**
	 * @param {number} index
	 */
	function openModal(index: number) {
		showModal = true;
		selectedImage = index;
		disableScroll();
	}

	function closeModal() {
		showModal = false;
		enableScroll();
	}

	/**
	 * @param {{ key: string; }} event
	 */
	function handleKeydown(event: KeyboardEvent) {
		if (showModal && searchResult) {
			if (event.key === 'Escape') {
				closeModal();
			} else if (event.key === 'ArrowRight') {
				selectedImage = (selectedImage + 1) % searchResult.hits.length;
			} else if (event.key === 'ArrowLeft') {
				selectedImage = (selectedImage - 1 + searchResult.hits.length) % searchResult.hits.length;
			}
		}
	}

	const disableScroll = () => {
		document.body.style.overflow = 'hidden';
	};

	const enableScroll = () => {
		document.body.style.overflow = '';
	};
</script>

<svelte:window on:keydown={handleKeydown} />

<div class="container mx-auto my-4">
	<Input
		type="text"
		class="w-full my-4 p-2 text-lg border-gray-500"
		bind:value={searchString}
		placeholder="Type to search..."
	/>
	<div class="flex space-x-2">
		<LibraryFilter bind:selectedLibraryIds={selectedLibraries} />
		<TimeFilter bind:start={startTimestamp} bind:end={endTimestamp} />
	</div>
</div>

<div class="container mx-auto flex">
	<!-- Left panel for tags and created_date -->
	<div class="w-1/5 pr-4">
		{#if searchResult && searchResult.facet_counts}
			{#each searchResult.facet_counts as facet}
				{#if facet.field_name === 'tags' || facet.field_name === 'created_date'}
					<FacetFilter
						{facet}
						selectedItems={facet.field_name === 'tags' ? selectedTags : selectedDates}
						onItemChange={facet.field_name === 'tags' ? handleTagChange : handleDateChange}
					/>
				{/if}
			{/each}
		{/if}
	</div>

	<!-- Right panel for search results -->
	<div class="w-4/5">
		{#if isLoading}
			<p>Loading...</p>
		{:else if searchResult && searchResult.hits.length > 0}
			<p class="search-summary mb-4">
				✨ {searchResult['found'].toLocaleString()} results found - Searched {searchResult[
					'out_of'
				].toLocaleString()} recipes in {searchResult['search_time_ms']}ms.
			</p>
			<div class="grid grid-cols-4 gap-4">
				{#each searchResult.hits as hit, index}
					<!-- svelte-ignore a11y-click-events-have-key-events -->
					<!-- svelte-ignore a11y-no-static-element-interactions -->
					<div
						class="bg-white rounded-lg overflow-hidden border border-gray-300 relative"
						on:click={() => openModal(index)}
					>
						<div class="px-4 pt-4">
							<h2 class="line-clamp-2 h-12">
								{hit.document.metadata_entries &&
								hit.document.metadata_entries.some((entry) => entry.key === 'active_window')
									? hit.document.metadata_entries.find((entry) => entry.key === 'active_window')
											.value
									: filename(hit.document.filepath)}
							</h2>
							<p class="text-gray-700 text-xs">
								{formatDistanceToNow(new Date(hit.document.file_created_at * 1000), {
									addSuffix: true
								})}
							</p>
						</div>
						<figure class="px-4 pt-4 mb-4 relative">
							<img
								class="w-full h-48 object-cover"
								src={`${apiEndpoint}/files/${hit.document.filepath}`}
								alt=""
							/>
							{#if hit.document.metadata_entries && hit.document.metadata_entries.some((entry) => entry.key === 'active_app')}
								<div
									class="absolute bottom-2 left-6 bg-white bg-opacity-75 px-2 py-1 rounded-full text-xs font-semibold border border-gray-200"
								>
									{hit.document.metadata_entries.find((entry) => entry.key === 'active_app').value}
								</div>
							{/if}
						</figure>
					</div>
				{/each}
			</div>
		{:else if searchString}
			<p>No results found.</p>
		{:else}
			<p>Type something to start searching...</p>
		{/if}
	</div>
</div>

{#if searchResult && searchResult.hits.length && showModal}
	<Figure
		id={searchResult.hits[selectedImage].document.id}
		library_id={searchResult.hits[selectedImage].document.library_id}
		folder_id={searchResult.hits[selectedImage].document.folder_id}
		image={`${apiEndpoint}/files/${searchResult.hits[selectedImage].document.filepath}`}
		video={`${apiEndpoint}/files/video/${searchResult.hits[selectedImage].document.filepath}`}
		created_at={searchResult.hits[selectedImage].document.file_created_at * 1000}
		filepath={searchResult.hits[selectedImage].document.filepath}
		title={filename(searchResult.hits[selectedImage].document.filepath)}
		tags={searchResult.hits[selectedImage].document.tags}
		metadata_entries={searchResult.hits[selectedImage].document.metadata_entries}
		onClose={closeModal}
		onNext={() => searchResult && openModal((selectedImage + 1) % searchResult.hits.length)}
		onPrevious={() =>
			searchResult &&
			openModal((selectedImage - 1 + searchResult.hits.length) % searchResult.hits.length)}
	/>
{/if}

<footer class="mx-auto mt-32 w-full container">
	<div class="border-t border-slate-900/5 py-10">
		<p class="mt-2 text-sm leading-6 text-slate-500">© 2023 Labs Inc. All rights reserved.</p>
		<div class="mt-2 flex items-center space-x-4 text-sm font-semibold leading-6 text-slate-700">
			<a href="/privacy-policy">Privacy policy</a>
			<div class="h-4 w-px bg-slate-500/20" />
			<a href="/changelog">Changelog</a>
		</div>
	</div>
</footer>
