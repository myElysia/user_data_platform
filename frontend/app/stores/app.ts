// ============================================================
// App Store — 全局 UI 状态
// ============================================================

import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useAppStore = defineStore('app', () => {
  const sidebarCollapsed = ref(false)
  const darkMode = ref(false)

  function toggleSidebar() {
    sidebarCollapsed.value = !sidebarCollapsed.value
  }

  function toggleDarkMode() {
    darkMode.value = !darkMode.value
    document.documentElement.classList.toggle('dark', darkMode.value)
  }

  return {
    sidebarCollapsed,
    darkMode,
    toggleSidebar,
    toggleDarkMode,
  }
})
