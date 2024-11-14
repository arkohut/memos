<script lang="ts">
	import { onMount } from 'svelte';
	import { locale, _ } from 'svelte-i18n';

	let selectedLocale: string;

	const languages = [
		{ value: 'en', label: 'English' },
		{ value: 'zh', label: '中文' }
	];

	onMount(() => {
		const savedLocale = localStorage.getItem('selectedLocale');
		if (savedLocale) {
			setLocale(savedLocale);
		} else {
			const browserLang = navigator.language.split('-')[0];
			setLocale(browserLang === 'zh' ? 'zh' : 'en');
		}
	});

	function setLocale(newLocale: string) {
		selectedLocale = newLocale;
		locale.set(newLocale);
		localStorage.setItem('selectedLocale', newLocale);
	}
</script>

<select
	bind:value={selectedLocale}
	on:change={() => setLocale(selectedLocale)}
	class="appearance-none bg-white text-slate-500 px-2 py-1 pr-8 rounded-md border border-slate-200 cursor-pointer hover:border-slate-300 focus:outline-none focus:ring-2 focus:ring-slate-200 focus:border-slate-300 text-sm font-medium relative bg-no-repeat bg-[right_0.5rem_center] bg-[length:1.5em_1.5em] bg-[url('data:image/svg+xml;charset=utf-8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%2020%2020%22%20fill%3D%22%236b7280%22%3E%3Cpath%20fill-rule%3D%22evenodd%22%20d%3D%22M5.293%207.293a1%201%200%20011.414%200L10%2010.586l3.293-3.293a1%201%200%20111.414%201.414l-4%204a1%201%200%2001-1.414%200l-4-4a1%201%200%20010-1.414z%22%20clip-rule%3D%22evenodd%22%2F%3E%3C%2Fsvg%3E')]"
>
	{#each languages as language}
		<option value={language.value}>{language.label}</option>
	{/each}
</select>