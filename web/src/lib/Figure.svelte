<!-- Modal.svelte -->
<script>
	import { ScrollArea } from "$lib/components/ui/scroll-area";
	import CopyToClipboard from "$lib/components/CopyToClipboard.svelte"
	import OCRTable from './OCRTable.svelte';
	import { marked } from 'marked';
	import { ChevronLeft, ChevronRight, X, Hash, Library, Folder, FileClock } from 'lucide-svelte';
	import { appIconMap } from '$lib/utils';
	import LucideIcon from '$lib/components/LucideIcon.svelte';

	/**
	 * @type {string}
	 */
	export let id;
	/**
	 * @type {number}
	 */
	export let library_id;
	/**
	 * @type {number}
	 */
	export let created_at;
	/**
	 * @type {number}
	 */
	export let folder_id;
	/**
	 * @type {any}
	 */
	export let image;
	/**
	 * @type {string}
	 */
	export let video;
	/**
	 * @type {string}
	 */
	export let filepath;
	/**
	 * @type {string}
	 */
	export let title;
	export let app_name;
	/**
	 * @type {Array<string>}
	 */
	export let tags = [];

	/**
	 * @type {Array<{key: string, source: string, value: any}>}
	 */
	export let metadata_entries = [];

	// Remove items with key "timestamp" or "sequence" and sort metadata_entries, placing "ocr_result" at the end
	$: sortedMetadataEntries = [...metadata_entries]
		.filter(entry => entry.key !== "timestamp" && entry.key !== "sequence" && entry.key !== "active_app" && entry.key !== "active_window")
		.sort((a, b) => {
			if (a.key === "ocr_result") return 1;
			if (b.key === "ocr_result") return -1;
			return 0;
		});

	/**
	 * @type {any}
	 */
	export let onClose;
	/**
	 * @type {any}
	 */
	export let onNext;
	/**
	 * @type {any}
	 */
	export let onPrevious;

	/**
	 * @param {any} data
	 * @returns {boolean}
	 */
	function isValidOCRDataStructure(data) {
		if (!Array.isArray(data)) return false;

		for (const item of data) {
			if (
				!item.hasOwnProperty('dt_boxes') ||
				!item.hasOwnProperty('rec_txt') ||
				!item.hasOwnProperty('score')
			) {
				return false;
			}

			if (
				!Array.isArray(item.dt_boxes) ||
				typeof item.rec_txt !== 'string' ||
				typeof item.score !== 'number'
			) {
				return false;
			}
		}

		return true;
	}
</script>

<div class="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-40" id="my-modal">
	<div
		class="relative top-10 mx-auto px-16 py-10 border w-11/12 max-w-10xl shadow-lg rounded-md bg-white group h-5/6"
	>
		<!-- Button container -->
		<div class="group">
			<button
				class="absolute left-2 top-1/2 transform -translate-y-1/2 text-white bg-gray-300 hover:bg-gray-400 font-bold rounded-full text-xl w-12 h-12 opacity-0 group-hover:opacity-85 flex items-center justify-center z-50"
				on:click={onPrevious}
			>
				<ChevronLeft size={32} />
			</button>
			<button
				class="absolute right-2 top-1/2 transform -translate-y-1/2 text-white bg-gray-300 hover:bg-gray-400 font-bold rounded-full text-xl w-12 h-12 opacity-0 group-hover:opacity-85 flex items-center justify-center z-50"
				on:click={onNext}
			>
				<ChevronRight size={32} />
			</button>
			<!-- Your modal content goes here -->
		</div>
		<div class="flex flex-col md:flex-row h-full">
			<!-- Image container -->
			<div class="flex-none w-full md:w-1/2 flex flex-col">
				<div class="mb-4">
					<div class="flex items-center space-x-2 text-lg leading-tight font-medium text-black hover:underline">
						<LucideIcon name={appIconMap[app_name] || 'Image'} size={24} />
						<p>{title}</p>
					</div>
				</div>
				<div class="mb-2 mr-2 pb-2 border-b border-gray-300">
					<span class="mt-1 text-sm leading-tight font-medium text-gray-500 font-mono">
						<span class="inline-flex mr-4">
							<Library size={16} class="uppercase tracking-wide text-sm text-indigo-600 font-bold mr-1"/>
							{library_id}
						</span>

						<span class="inline-flex mr-4">
							<Folder size={16} class="uppercase tracking-wide text-sm text-indigo-600 font-bold mr-1"/>
							{folder_id}
						</span>

						<span class="inline-flex mr-4">
							<Hash size={16} class="uppercase tracking-wide text-sm text-indigo-600 font-bold mr-1"/>
							{id}
						</span>

						<span class="inline-flex mr-4">
							<FileClock size={16} class="uppercase tracking-wide text-sm text-indigo-600 font-bold mr-1"/>
							{new Date(created_at).toLocaleString()}
						</span>
					</span>

					<div>
						<span class="mt-1 text-xs leading-tight font-xs text-gray-500 font-mono">
							{filepath}
						</span>
					</div>
				</div>
				<div class="flex-grow overflow-hidden">
					<a href={video} target="_blank" rel="noopener noreferrer" class="block h-full">
						<img 
							class="w-full h-full object-contain rounded-lg drop-shadow-md" 
							src={image} 
							alt={title} 
						/>
					</a>
				</div>
			</div>
			<!-- Description container -->
			<ScrollArea class="mt-4 md:mt-0 md:ml-6 overflow-y-auto max-h-full">
				
				{#if tags.length > 0}
					<div class="mb-4">
						<div class="uppercase tracking-wide text-sm text-indigo-600 font-bold">TAGS</div>
						<div class=" text-gray-600">
						{#each tags as tag}
							<span class="text-base text-gray-500 inline-block">{tag}</span>
							{/each}
						</div>
					</div>
				{/if}
				<div class="uppercase tracking-wide text-sm text-indigo-600 font-bold">METADATA</div>
				<div class="mt-2 text-gray-600">
					{#each sortedMetadataEntries as entry}
						<div class="mb-2">
							<span class="font-bold flex items-center">
								{entry.key}
								<CopyToClipboard text={entry.value} />
							</span>
							{#if typeof entry.value === 'object'}
								{#if isValidOCRDataStructure(entry.value)}
									<OCRTable ocrData={entry.value} />
								{:else}
									<pre class="bg-gray-100 p-2 rounded overflow-y-auto max-h-96">{JSON.stringify(
											entry.value,
											null,
											2
										)}</pre>
								{/if}
							{:else}
								<!-- Render markdown content -->
								<div class="prose">
									{@html marked(entry.value)}
								</div>
							{/if}
							<span class="text-sm text-gray-500">({entry.source})</span>
						</div>
					{/each}
				</div>
			</ScrollArea>
		</div>
		<div class="absolute top-0 right-0 pt-2 pr-2">
			<button class="text-gray-400 hover:text-gray-600 opacity-0 group-hover:opacity-100" on:click={onClose}>
				<!-- svelte-ignore a11y-click-events-have-key-events -->
				<!-- svelte-ignore a11y-no-static-element-interactions -->
				<X size={32} />
			</button>
		</div>
	</div>
</div>
