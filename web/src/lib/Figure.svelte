<!-- Modal.svelte -->
<script>
	import OCRTable from './OCRTable.svelte';
	import { marked } from 'marked';

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
	export let filepath;
	/**
	 * @type {string}
	 */
	export let title;
	/**
	 * @type {Array<string>}
	 */
	export let tags = [];

	/**
	 * @type {Array<{key: string, source: string, value: any}>}
	 */
	export let metadata_entries = [];
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

	/**
	 * Copy text to clipboard
	 * @param {string} text
	 */
	 function copyToClipboard(text) {
		navigator.clipboard.writeText(text).then(() => {
			console.log('Text copied to clipboard');
		}).catch(err => {
			console.error('Failed to copy text: ', err);
		});
	}
</script>

<div class="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full" id="my-modal">
	<div
		class="relative top-10 mx-auto p-10 border w-11/12 max-w-10xl shadow-lg rounded-md bg-white group h-5/6"
	>
		<!-- Button container -->
		<div class="group">
			<button
				class="absolute left-5 top-1/2 transform -translate-y-1/2 text-white bg-gray-300 hover:bg-gray-400 font-bold rounded-full text-2xl w-12 h-12 opacity-0 group-hover:opacity-100"
				on:click={onPrevious}
			>
				&lt;
			</button>
			<button
				class="absolute right-5 top-1/2 transform -translate-y-1/2 text-white bg-gray-300 hover:bg-gray-400 font-bold rounded-full text-2xl w-12 h-12 opacity-0 group-hover:opacity-100"
				on:click={onNext}
			>
				&gt;
			</button>
			<!-- Your modal content goes here -->
		</div>
		<div class="flex flex-col md:flex-row h-full">
			<!-- Image container -->
			<div class="flex-none w-full md:w-1/2 h-full">
				<a href={image} target="_blank" rel="noopener noreferrer">
					<img class="w-full h-full object-contain" src={image} alt={title} />
				</a>
			</div>
			<!-- Description container -->
			<div class="mt-4 md:mt-0 md:ml-6 overflow-y-auto max-h-full">
				<div class="mb-2 mr-2 pb-2 border-b border-gray-300">
					<span class="uppercase tracking-wide text-sm text-indigo-600 font-bold">ID</span>
					<span class="mt-1 text-sm leading-tight font-medium text-gray-500 font-mono">
						{id}
					</span>
					<span class="uppercase tracking-wide text-sm text-indigo-600 font-bold ml-4"
						>Library ID</span
					>
					<span class="mt-1 text-sm leading-tight font-medium text-gray-500 font-mono">
						{library_id}
					</span>
					<span class="uppercase tracking-wide text-sm text-indigo-600 font-bold ml-4"
						>Folder ID</span
					>
					<span class="mt-1 text-sm leading-tight font-medium text-gray-500 font-mono">
						{folder_id}
					</span>
					<span class="uppercase tracking-wide text-sm text-indigo-600 font-bold ml-4"
						>DATETIME</span
					>
					<span class="mt-1 text-xs leading-tight font-xs text-gray-500 font-mono">
						{new Date(created_at * 1000).toLocaleString()}
					</span>
					<div>
						<span class="mt-1 text-xs leading-tight font-xs text-gray-500 font-mono">
							{filepath}
						</span>
					</div>
				</div>
				<div class="uppercase tracking-wide text-sm text-indigo-600 font-bold">Image Title</div>
				<p class="block mt-1 text-lg leading-tight font-medium text-black hover:underline">
					{title}
				</p>
				<div class="uppercase tracking-wide text-sm text-indigo-600 font-bold">TAGS</div>
				<div class="mt-2 text-gray-600">
					{#each tags as tag}
						<span class="text-base text-gray-500 inline-block">{tag}</span>
					{/each}
				</div>
				<div class="uppercase tracking-wide text-sm text-indigo-600 font-bold">METADATA</div>
				<div class="mt-2 text-gray-600">
					{#each metadata_entries as entry}
						<div class="mb-2">
							<span class="font-bold flex items-center">
								{entry.key}
								<button class="ml-2 flex items-center" on:click={() => copyToClipboard(entry.value)}>
									<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor" style="margin-top: -4px;">
										<path d="M8 3a1 1 0 011-1h2a1 1 0 110 2H9a1 1 0 01-1-1z" />
										<path d="M6 3a2 2 0 00-2 2v11a2 2 0 002 2h8a2 2 0 002-2V5a2 2 0 00-2-2 3 3 0 01-3 3H9a3 3 0 01-3-3z" />
									</svg>
								</button>
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
			</div>
		</div>
		<div class="absolute top-0 right-0 pt-4 pr-4">
			<button class="text-gray-400 hover:text-gray-600" on:click={onClose}>
				<!-- svelte-ignore a11y-click-events-have-key-events -->
				<!-- svelte-ignore a11y-no-static-element-interactions -->
				<span class="text-2xl">&times;</span>
			</button>
		</div>
	</div>
</div>
