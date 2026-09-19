/**
 * UI Component Library
 * Premium components for the Editorrah classroom system
 */

// Components
export { default as UiButton } from './Button.vue'
export { default as UiCard } from './Card.vue'
export { default as UiInput } from './Input.vue'
export { default as UiModal } from './Modal.vue'
export { default as UiBadge } from './Badge.vue'
export { default as UiSkeleton } from './Skeleton.vue'
export { default as UiToast } from './Toast.vue'
export { default as UiAvatar } from './Avatar.vue'
export { default as UiProgress } from './Progress.vue'
export { default as UiTabs } from './Tabs.vue'
export { default as UiDropdown } from './Dropdown.vue'

// Plugin for global registration
export default {
  install(app) {
    app.component('UiButton', () => import('./Button.vue'))
    app.component('UiCard', () => import('./Card.vue'))
    app.component('UiInput', () => import('./Input.vue'))
    app.component('UiModal', () => import('./Modal.vue'))
    app.component('UiBadge', () => import('./Badge.vue'))
    app.component('UiSkeleton', () => import('./Skeleton.vue'))
    app.component('UiToast', () => import('./Toast.vue'))
    app.component('UiAvatar', () => import('./Avatar.vue'))
    app.component('UiProgress', () => import('./Progress.vue'))
    app.component('UiTabs', () => import('./Tabs.vue'))
    app.component('UiDropdown', () => import('./Dropdown.vue'))
  }
}
