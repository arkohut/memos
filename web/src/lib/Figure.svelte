<!-- Modal.svelte -->
<script>
	/**
	 * @type {any}
	 */
	export let image;
	/**
	 * @type {any}
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
				<img class="w-full h-full object-contain" src={image} alt={title} />
			</div>
			<!-- Description container -->
			<div class="mt-4 md:mt-0 md:ml-6 overflow-y-auto max-h-full">
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
							<span class="font-bold">{entry.key}:</span>
							{#if typeof entry.value === 'object'}
								<pre class="bg-gray-100 p-2 rounded overflow-y-auto max-h-96">{JSON.stringify(entry.value, null, 2)}</pre>
							{:else}
								{entry.value}
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