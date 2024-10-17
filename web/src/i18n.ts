import { init, register } from 'svelte-i18n';

register('en', () => import('./locales/en.json'));
register('zh', () => import('./locales/zh.json'));

init({
    fallbackLocale: 'en',
    initialLocale: 'zh', // 或者根据用户的浏览器设置动态选择
});