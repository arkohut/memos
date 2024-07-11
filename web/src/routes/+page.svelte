<script>
	import Figure from '$lib/Figure.svelte';
	import { PUBLIC_API_ENDPOINT } from '$env/static/public';

	let searchString = '';
	/**
	 * @type {any[]}
	 */
	let searchResults = [];
	let isLoading = false;
	let debounceTimer;
	let showModal = false;
	let selectedImage = 0;

	const debounceDelay = 300;
	const apiEndpoint =
		typeof PUBLIC_API_ENDPOINT !== 'undefined' ? PUBLIC_API_ENDPOINT : window.location.origin;

	/**
	 * @param {string} query
	 */
	async function searchItems(query) {
		isLoading = true;

		try {
			const response = await fetch(`${apiEndpoint}/search?q=${encodeURIComponent(query)}`);
			if (!response.ok) {
				throw new Error('Network response was not ok');
			}
			searchResults = await response.json();
			console.log(searchResults);
		} catch (error) {
		} finally {
			isLoading = false;
		}
	}

	/**
	 * @param {string} query
	 */
	function debounceSearch(query) {
		clearTimeout(debounceTimer);
		debounceTimer = setTimeout(() => {
			searchItems(query);
		}, debounceDelay);
	}

	/**
	 * @param {string} path
	 */
	function filename(path) {
		let splits = path.split('/');
		return splits[splits.length - 1];
	}

	/**
	 * @param {number} index
	 */
	function openModal(index) {
		// @ts-ignore
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
	function handleKeydown(event) {
		if (showModal) {
			if (event.key === 'Escape') {
				closeModal();
			} else if (event.key === 'ArrowRight') {
				selectedImage = (selectedImage + 1) % searchResults.length;
			} else if (event.key === 'ArrowLeft') {
				selectedImage = (selectedImage - 1 + searchResults.length) % searchResults.length;
			}
		}
	}

	const disableScroll = () => {
		document.body.style.overflow = 'hidden';
	};

	const enableScroll = () => {
		document.body.style.overflow = '';
	};

	$: if (searchString.trim()) {
		debounceSearch(searchString);
	} else {
		searchResults = [];
	}
</script>

<svelte:window on:keydown={handleKeydown} />

<div class="container mx-auto my-10">
	<input
		type="text"
		class="input input-bordered w-full my-4 p-2 text-lg border border-gray-500"
		bind:value={searchString}
		placeholder="Type to search..."
	/>
</div>

<div class="container mx-auto">
	{#if isLoading}
		<p>Loading...</p>
	{:else if searchString}
		<div class="grid grid-cols-4 gap-4">
			{#each searchResults as item, index}
				<!-- svelte-ignore a11y-click-events-have-key-events -->
				<!-- svelte-ignore a11y-no-static-element-interactions -->
				<div
					class="bg-white rounded-lg overflow-hidden shadow-md hover:shadow-xl transition-shadow duration-300 ease-in-out"
					on:click={() => openModal(index)}
				>
					<figure class="px-5 pt-5">
						<img
							class="w-full h-48 object-cover"
							src={`${apiEndpoint}/files/${item.filepath}`}
							alt=""
						/>
					</figure>
					<div class="p-4">
						<h2 class="text-lg font-bold mb-2">{filename(item.filepath)}</h2>
						<p class="text-gray-700 line-clamp-5">{''}</p>
					</div>
				</div>
			{/each}
		</div>
	{:else}
		<p>Type something to start searching...</p>
	{/if}
</div>

{#if searchResults.length && showModal}
	<Figure
		id={searchResults[selectedImage].id}
		image={`${apiEndpoint}/files/${searchResults[selectedImage].filepath}`}
		title={filename(searchResults[selectedImage].filepath)}
		tags={searchResults[selectedImage].tags}
		metadata_entries={searchResults[selectedImage].metadata_entries}
		onClose={closeModal}
		onNext={() => openModal((selectedImage + 1) % searchResults.length)}
		onPrevious={() => openModal((selectedImage - 1 + searchResults.length) % searchResults.length)}
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
