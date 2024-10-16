<script lang="ts">
	import Figure from '$lib/Figure.svelte';
	import TimeFilter from '$lib/components/TimeFilter.svelte';
	import LibraryFilter from '$lib/components/LibraryFilter.svelte';
	import { Input } from '$lib/components/ui/input';
	import { PUBLIC_API_ENDPOINT } from '$env/static/public';
	import FacetFilter from '$lib/components/FacetFilter.svelte';
	import { formatDistanceToNow } from 'date-fns';
	import Logo from '$lib/components/Logo.svelte';
	import { onMount } from 'svelte';
	import { translateAppName } from '$lib/utils';
	import LucideIcon from '$lib/components/LucideIcon.svelte';

	let searchString = '';
	/**
	 * @type {any[]}
	 */
	let searchResults = [];
	let isLoading = false;
	let debounceTimer: ReturnType<typeof setTimeout>;
	let showModal = false;
	let selectedImage = 0;

	let startTimestamp: number | null = null;
	let endTimestamp: number | null = null;

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

	const debounceDelay = 500;
	const apiEndpoint =
		typeof PUBLIC_API_ENDPOINT !== 'undefined' ? PUBLIC_API_ENDPOINT : window.location.origin;

	let facetCounts: Facet[] | null = null;

	let isScrolled = false;
	let headerElement: HTMLElement;

	// 添加一个计算属性来生成输入框的类名
	$: inputClasses = `w-full p-2 text-lg border-gray-500 transition-all duration-300 ${
		!isScrolled ? 'mt-4' : ''
	}`;

	onMount(() => {
		const handleScroll = () => {
			console.log(window.scrollY)
			if (window.scrollY > 100) {
				isScrolled = true;
			} else if (isScrolled && window.scrollY < 20) {
				isScrolled = false;
			}
		};

		window.addEventListener('scroll', handleScroll);

		return () => {
			window.removeEventListener('scroll', handleScroll);
		};
	});

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
		console.log('handleSearchStringChange', searchString);
		clearTimeout(debounceTimer);
		if (searchString.trim()) {
			debounceTimer = setTimeout(() => {
				searchItems(
					searchString,
					startTimestamp,
					endTimestamp,
					selectedLibraries,
					Object.keys(selectedTags).filter((tag) => selectedTags[tag]),
					Object.keys(selectedDates).filter((date) => selectedDates[date]),
					true
				);
			}, debounceDelay);
		} else {
			searchResults = [];
			searchResult = null;
			facetCounts = null;
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

	function handleFiltersChange() {
		searchItems(
			searchString,
			startTimestamp,
			endTimestamp,
			selectedLibraries,
			Object.keys(selectedTags).filter((tag) => selectedTags[tag]),
			Object.keys(selectedDates).filter((date) => selectedDates[date]),
			false
		);
	}

	$: {
		if (startTimestamp != null || endTimestamp != null || selectedLibraries.length > 0) {
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

	function handleEnterPress(event: KeyboardEvent) {
		if (event.key === 'Enter') {
			event.preventDefault();
			searchItems(
				searchString,
				startTimestamp,
				endTimestamp,
				selectedLibraries,
				Object.keys(selectedTags).filter((tag) => selectedTags[tag]),
				Object.keys(selectedDates).filter((date) => selectedDates[date]),
				true
			);
		}
	}

	// Add this function near the top of the <script> section
	function getEntityTitle(document: any): string {
		if (document.metadata_entries && 
			document.metadata_entries.some((entry: any) => entry.key === 'active_window')) {
			return document.metadata_entries.find((entry: any) => entry.key === 'active_window').value;
		}
		return filename(document.filepath);
	}

	function getAppName(document: any): string {
		if (document.metadata_entries && document.metadata_entries.some((entry: any) => entry.key === 'active_app')) {
			return document.metadata_entries.find((entry: any) => entry.key === 'active_app').value;
		} else {
			return "unknown";
		}
	}

</script>

<svelte:head>
	<title>memos {searchString ? `- ${searchString}` : ''}</title>
</svelte:head>

<svelte:window on:keydown={handleKeydown} />

<header
	class="sticky top-0 z-10 transition-all duration-300"
	bind:this={headerElement}
>
	<div class="mx-auto max-w-screen-lg flex items-center justify-between p-4 transition-all duration-300"
		 class:flex-col={!isScrolled}
		 class:flex-row={isScrolled}
	>
		<Logo size={isScrolled ? 32 : 128} withBorder={!isScrolled} class_="transition-transform duration-300 ease-in-out mr-4" />
		<Input
			type="text"
			class={inputClasses}
			bind:value={searchString}
			placeholder="Input keyword to search or press Enter to show latest records"
			on:keydown={handleEnterPress}
			autofocus
		/>
		<div class="mx-auto max-w-screen-lg">
			<div class="flex space-x-2" class:mt-4={!isScrolled} class:ml-4={isScrolled}>
				<LibraryFilter bind:selectedLibraryIds={selectedLibraries} />
				<TimeFilter bind:start={startTimestamp} bind:end={endTimestamp} />
			</div>
		</div>
	</div>
</header>

<!-- 添加一个动态调整高度的空白区域 -->
<div style="height: {isScrolled ? '100px' : '0px'}"></div>

<div class="mx-auto flex flex-col sm:flex-row">
	<!-- Left panel for tags and created_date -->
	{#if searchResult && searchResult.facet_counts && searchResult.facet_counts.length > 0}
	<div class="xl:w-1/7 lg:w-1/6 md:w-1/5 sm:w-full pr-4">
		{#each searchResult.facet_counts as facet}
			{#if facet.field_name === 'tags' || facet.field_name === 'created_date'}
				<FacetFilter
					{facet}
					selectedItems={facet.field_name === 'tags' ? selectedTags : selectedDates}
					onItemChange={facet.field_name === 'tags' ? handleTagChange : handleDateChange}
				/>
			{/if}
		{/each}
	</div>
	{/if}

	<!-- Right panel for search results -->
	<div class="{searchResult && searchResult.facet_counts && searchResult.facet_counts.length > 0 ? 'xl:w-6/7 lg:w-5/6 md:w-4/5' : 'w-full'}">
		{#if isLoading}
			<p class="text-center">Loading...</p>
		{:else if searchResult && searchResult.hits.length > 0}
			{#if searchResult['search_time_ms'] > 0}
				<p class="search-summary mb-4 text-center">
					✨ {searchResult['found'].toLocaleString()} results found - Searched {searchResult[
						'out_of'
					].toLocaleString()} recipes in {searchResult['search_time_ms']}ms.
				</p>
			{/if}
			<div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
				{#each searchResult.hits as hit, index}
					<!-- svelte-ignore a11y-click-events-have-key-events -->
					<!-- svelte-ignore a11y-no-static-element-interactions -->
					<div
						class="bg-white rounded-lg overflow-hidden border border-gray-300 relative"
						on:click={() => openModal(index)}
					>
						<div class="px-4 pt-4">
							<h2 class="line-clamp-2 h-12">
								{getEntityTitle(hit.document)}
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
							{#if getAppName(hit.document)}
								<div
									class="absolute bottom-2 left-6 bg-white bg-opacity-75 px-2 py-1 rounded-full text-xs font-semibold border border-gray-200 flex items-center space-x-2"
								>
									<LucideIcon name={translateAppName(getAppName(hit.document)) || "Hexagon"} size={16} />
									<span>{getAppName(hit.document)}</span>
								</div>
							{/if}
						</figure>
					</div>
				{/each}
			</div>
		{:else if searchString}
			<p class="text-center">No results found.</p>
		{:else}
			<p class="text-center"></p>
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
		title={getEntityTitle(searchResult.hits[selectedImage].document)}
		app_name={getAppName(searchResult.hits[selectedImage].document)}
		tags={searchResult.hits[selectedImage].document.tags}
		metadata_entries={searchResult.hits[selectedImage].document.metadata_entries}
		onClose={closeModal}
		onNext={() => searchResult && openModal((selectedImage + 1) % searchResult.hits.length)}
		onPrevious={() =>
			searchResult &&
			openModal((selectedImage - 1 + searchResult.hits.length) % searchResult.hits.length)}
	/>
{/if}

<footer class="mx-auto mt-32 w-full container text-center">
	<div class="border-t border-slate-900/5 py-10">
		<p class="mt-2 text-sm leading-6 text-slate-500">© 2024 Arkohut Qinini. All rights reserved.</p>
		<div class="mt-2 flex justify-center items-center space-x-4 text-sm font-semibold leading-6 text-slate-700">
			<a href="/privacy-policy">Privacy policy</a>
			<div class="h-4 w-px bg-slate-500/20" />
			<a href="/changelog">Changelog</a>
		</div>
	</div>
</footer>
