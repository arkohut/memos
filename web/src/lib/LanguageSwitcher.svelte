<script lang="ts">
	import { onMount } from 'svelte';
	import { locale, _ } from 'svelte-i18n';

	let selectedLocale: string;

	const languages = [
		{ value: 'en', label: 'English' },
		{ value: 'zh', label: '中文' }
	];

	onMount(() => {
		// 尝试从 localStorage 获取保存的语言
		const savedLocale = localStorage.getItem('selectedLocale');
		if (savedLocale) {
			setLocale(savedLocale);
		} else {
			// 如果没有保存的语言,则使用浏览器语言
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

<select bind:value={selectedLocale} on:change={() => setLocale(selectedLocale)} class="bg-white text-slate-500">
    {#each languages as language}
        <option value={language.value}>{language.label}</option>
    {/each}
</select>