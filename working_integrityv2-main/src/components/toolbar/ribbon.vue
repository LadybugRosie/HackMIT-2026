<template>
  <div class="ribbon-menu">
    <div v-if="menus.length > 1" class="ribbon-tabs">
      <div
        class="tabs-item"
        :class="{ 
          active: currentMenu === item.value,
          'latex-tab': item.value === 'latex'
        }"
        v-for="item in menus"
        :key="item.value"
        @click="changeMenu(item.value)"
      >
        {{ item.label }}
      </div>
    </div>
    <toolbar-scrollable ref="scrollableRef" class="scrollable-container">
      <div class="ribbon-container">
        <template v-if="currentMenu === 'base'">
          <div class="virtual-group">
            <div class="virtual-group-row">
              <menus-toolbar-base-undo />
              <menus-toolbar-base-redo />
            </div>
            <div class="virtual-group-row">
              <menus-toolbar-base-format-painter />
              <menus-toolbar-base-clear-format />
            </div>
          </div>
          <div class="virtual-group">
            <div class="virtual-group-row">
              <menus-toolbar-base-font-family />
              <menus-toolbar-base-font-size />
            </div>
            <div class="virtual-group-row">
              <menus-toolbar-base-bold />
              <menus-toolbar-base-italic />
              <menus-toolbar-base-underline />
              <menus-toolbar-base-strike />
              <menus-toolbar-base-subscript />
              <menus-toolbar-base-superscript />
              <menus-toolbar-base-color />
              <menus-toolbar-base-background-color />
              <menus-toolbar-base-highlight />
            </div>
          </div>
          <div class="virtual-group">
            <div class="virtual-group-row">
              <menus-toolbar-base-ordered-list />
              <menus-toolbar-base-bullet-list />
              <menus-toolbar-base-task-list />
              <menus-toolbar-base-indent />
              <menus-toolbar-base-outdent />
              <menus-toolbar-base-line-height />
              <menus-toolbar-base-margin />
            </div>
            <div class="virtual-group-row">
              <menus-toolbar-base-align-left />
              <menus-toolbar-base-align-center />
              <menus-toolbar-base-align-right />
              <menus-toolbar-base-align-justify />
              <menus-toolbar-base-align-distributed />
              <menus-toolbar-base-quote />
              <menus-toolbar-base-code v-if="!disableItem('code')" />
              <menus-toolbar-base-select-all />
            </div>
          </div>
          <div class="virtual-group">
            <menus-toolbar-base-heading />
          </div>
          <div class="virtual-group">
            <menus-toolbar-base-import-word />
            <menus-toolbar-base-markdown />
            <menus-toolbar-base-search-replace />
          </div>
          <div class="virtual-group">
            <menus-toolbar-base-print v-if="!disableItem('print')" />
          </div>
          <div class="virtual-group is-slot">
            <slot name="toolbar_base" toolbar-mode="ribbon" />
          </div>
        </template>
        <template v-if="currentMenu === 'insert'">
          <div class="virtual-group">
            <menus-toolbar-insert-link />
            <menus-toolbar-insert-image />
            <menus-toolbar-insert-video v-if="!disableItem('video')" />
            <menus-toolbar-insert-audio v-if="!disableItem('audio')" />
            <menus-toolbar-insert-file v-if="!disableItem('file')" />
            <menus-toolbar-insert-code-block
              v-if="!disableItem('code-block')"
            />
            <menus-toolbar-insert-symbol />
            <menus-toolbar-insert-chinese-date
              v-if="!disableItem('chineseDate')"
            />
            <menus-toolbar-insert-emoji v-if="!disableItem('emoji')" />
            <menus-toolbar-insert-math v-if="!disableItem('math')" />
          </div>
          <div class="virtual-group">
            <menus-toolbar-insert-hard-break />
            <menus-toolbar-insert-hr />
            <menus-toolbar-insert-toc />
            <menus-toolbar-insert-text-box />
          </div>
          <div class="virtual-group">
            <menus-toolbar-insert-template />
            <menus-toolbar-insert-web-page />
          </div>
          <div class="virtual-group is-slot">
            <slot name="toolbar_insert" toolbar-mode="ribbon" />
          </div>
        </template>
        <template v-if="currentMenu === 'table'">
          <div class="virtual-group">
            <menus-toolbar-table-insert />
            <menus-toolbar-table-fix />
          </div>
          <div class="virtual-group">
            <menus-toolbar-table-cells-align />
            <menus-toolbar-table-cells-background />
            <!-- <menus-toolbar-table-border-color /> -->
          </div>
          <div class="virtual-group">
            <div class="virtual-group-row">
              <menus-toolbar-table-add-row-before />
              <menus-toolbar-table-add-row-after />
              <menus-toolbar-table-delete-row />
            </div>
            <div class="virtual-group-row">
              <menus-toolbar-table-add-column-before />
              <menus-toolbar-table-add-column-after />
              <menus-toolbar-table-delete-column />
            </div>
          </div>
          <div class="virtual-group">
            <div class="virtual-group-row">
              <menus-toolbar-table-merge-cells />
            </div>
            <div class="virtual-group-row">
              <menus-toolbar-table-split-cell />
            </div>
          </div>
          <div class="virtual-group">
            <div class="virtual-group-row">
              <menus-toolbar-table-toggle-header-row />
              <menus-toolbar-table-toggle-header-column />
            </div>
            <div class="virtual-group-row">
              <menus-toolbar-table-toggle-header-cell />
            </div>
          </div>
          <div class="virtual-group">
            <div class="virtual-group-row">
              <menus-toolbar-table-next-cell />
            </div>
            <div class="virtual-group-row">
              <menus-toolbar-table-previous-cell />
            </div>
          </div>
          <div class="virtual-group">
            <menus-toolbar-table-delete />
          </div>
          <div class="virtual-group is-slot">
            <slot name="toolbar_table" toolbar-mode="ribbon" />
          </div>
        </template>
        <template v-if="currentMenu === 'tools'">
          <div class="virtual-group">
            <menus-toolbar-tools-citation/>
            <menus-toolbar-tools-qrcode />
            <menus-toolbar-tools-barcode />
          </div>
          <div class="virtual-group">
            <menus-toolbar-tools-signature v-if="!disableItem('signature')" />
            <menus-toolbar-tools-seal v-if="!disableItem('seal')" />
          </div>
          <div class="virtual-group">
            <menus-toolbar-tools-diagrams v-if="!disableItem('diagrams')" />
            <!-- <menus-toolbar-tools-mind-map v-if="!disableItem('mind-map')" /> -->
            <menus-toolbar-tools-mermaid v-if="!disableItem('mermaid')" />
          </div>
          <div class="virtual-group">
            <menus-toolbar-tools-chinese-case
              v-if="!disableItem('chineseCase')"
            />
          </div>
          <div class="virtual-group">
            <slot name="toolbar_tools" toolbar-mode="ribbon" />
          </div>
        </template>
        <template v-if="currentMenu === 'page'">
          <div class="virtual-group">
            <menus-toolbar-page-toggle-toc />
          </div>
          <div class="virtual-group">
            <div class="virtual-group-row">
              <menus-toolbar-page-margin />
              <div>
                <div class="virtual-group-row">
                  <menus-toolbar-page-size />
                </div>
                <div class="virtual-group-row">
                  <menus-toolbar-page-orientation />
                </div>
              </div>
            </div>
          </div>
          <div class="virtual-group" v-if="!hidePageHeader || !hidePageFooter">
            <menus-toolbar-page-header v-if="!hidePageHeader" />
            <menus-toolbar-page-footer v-if="!hidePageFooter" />
          </div>
          <div class="virtual-group">
            <menus-toolbar-page-break />
            <menus-toolbar-page-line-number />
            <menus-toolbar-page-watermark />
            <menus-toolbar-page-background />
          </div>
          <div class="virtual-group">
            <menus-toolbar-page-preview />
          </div>
          <div class="virtual-group is-slot">
            <slot name="toolbar_page" toolbar-mode="ribbon" />
          </div>
        </template>
        <template v-if="currentMenu === 'export'">
          <div class="virtual-group">
            <menus-toolbar-export-image />
            <menus-toolbar-export-pdf />
            <!-- <menus-toolbar-export-html /> -->
            <menus-toolbar-export-text />
          </div>
          <div class="virtual-group">
            <menus-toolbar-export-share v-if="!disableItem('share')" />
            <menus-toolbar-export-embed v-if="!disableItem('embed')" />
          </div>
          <div class="virtual-group is-slot">
            <slot name="toolbar_export" toolbar-mode="ribbon" />
          </div>
        </template>
        <template v-if="currentMenu === 'latex'">
          <div class="virtual-group latex-group">
            <menus-toolbar-export-latex />
          </div>
          <div class="virtual-group is-slot">
            <slot name="toolbar_latex" toolbar-mode="ribbon" />
          </div>
        </template>
      </div>
    </toolbar-scrollable>
  </div>
</template>

<script setup>
const props = defineProps({
  menus: {
    type: Array,
    required: true,
  },
  currentMenu: {
    type: String,
    required: true,
  },
})
const emits = defineEmits(['menu-change'])

const { options, hidePageHeader, hidePageFooter } = useStore()
const disableItem = (name) => {
  return options.value.toolbar.disableMenuItems.includes(name)
}

const scrollableRef = $ref()
const changeMenu = async (menu) => {
  emits('menu-change', menu)
  await nextTick()
  scrollableRef.update()
}
</script>

<style lang="less" scoped>
.ribbon-menu {
  width: 100%;
}
.ribbon-tabs {
  padding: 10px 10px 0;
  display: flex;
  .tabs-item {
    font-size: var(--umo-font-size-small);
    margin-right: 25px;
    cursor: pointer;
    display: flex;
    align-items: center;
    flex-direction: column;
    position: relative;
    transition: all 0.3s ease;
    
    &:hover {
      font-weight: 600;
      &::after {
        display: block;
        content: '';
        height: 3px;
        width: 100%;
        margin-top: 5px;
        background-color: var(--umo-border-color);
      }
    }
    &.active {
      color: var(--umo-primary-color);
      font-weight: 600;
      &::after {
        display: block;
        content: '';
        height: 3px;
        width: 100%;
        margin-top: 5px;
        background-color: var(--umo-primary-color);
        transition: width 0.3s;
      }
      &:hover::after {
        width: 120%;
      }
    }
    
    // Magical styling for LaTeX tab
    &.latex-tab {
      background: linear-gradient(135deg, rgba(147, 197, 253, 0.2) 0%, rgba(196, 181, 253, 0.2) 50%, rgba(251, 191, 36, 0.2) 100%);
      border-radius: 6px;
      position: relative;
      overflow: hidden;
      
      
      &:hover {
        background: linear-gradient(135deg, rgba(147, 197, 253, 0.3) 0%, rgba(196, 181, 253, 0.3) 50%, rgba(251, 191, 36, 0.3) 100%);
        box-shadow: 0 2px 8px rgba(147, 197, 253, 0.3);
        
        &::after {
          background: linear-gradient(135deg, #93c5fd 0%, #c4b5fd 50%, #fbbf24 100%);
        }
      }
      
      &.active {
        background: linear-gradient(135deg, rgba(147, 197, 253, 0.4) 0%, rgba(196, 181, 253, 0.4) 50%, rgba(251, 191, 36, 0.4) 100%);
        color: #1e40af;
        
        &::after {
          background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 50%, #f59e0b 100%);
        }
      }
    }
    
    
    @media screen and (max-width: 640px) {
      margin-right: 10px;
      
      &.latex-tab {
        margin-right: 10px;
      }
    }
  }
}
.scrollable-container {
  width: 100%;
  padding: 10px;
  box-sizing: border-box;
}
.ribbon-container {
  display: flex;
  height: 56px;
  flex-shrink: 0;
  .virtual-group {
    padding: 0 20px;
    border-left: solid 1px var(--umo-border-color-light);
    flex-shrink: 0;
    &:empty {
      display: none;
    }
    &:first-child {
      padding-left: 0;
    }
    &:first-child,
    &.is-slot:empty {
      border-left: none;
    }
    
    &.latex-group {
      background: linear-gradient(135deg, rgba(147, 197, 253, 0.1) 0%, rgba(196, 181, 253, 0.1) 50%, rgba(251, 191, 36, 0.1) 100%);
      border-radius: 12px;
      margin: 5px;
      padding: 0 25px;
      border-left: none;
      position: relative;
      display: flex;
      align-items: center;
      height: 46px;
      
      &::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: linear-gradient(135deg, rgba(147, 197, 253, 0.05) 0%, rgba(196, 181, 253, 0.05) 50%, rgba(251, 191, 36, 0.05) 100%);
        border-radius: 12px;
        z-index: -1;
      }
    }
    
    &-row {
      display: flex;
      align-items: center;
      :deep(> *:not(:last-child)) {
        margin-right: 5px;
      }
      &:not(:last-child) {
        margin-bottom: 5px;
      }
    }
  }
}
</style>
