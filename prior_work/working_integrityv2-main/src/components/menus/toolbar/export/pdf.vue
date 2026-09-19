<template>
  <menus-button
    text="PDF"
    ico="pdf"
    shortcut="Ctrl+P"
    huge
    @menu-click="handleExportPDF"
  >
  </menus-button>
</template>

<script setup>
import { useIntegrityExport } from '@/composables/integrity-export'

const { exportPDF } = useStore()
const { checkExportAllowed } = useIntegrityExport()

const handleExportPDF = async () => {
  const allowed = await checkExportAllowed(60)
  if (allowed) {
    exportPDF.value = true
  }
}
</script> 
<style lang="less" scoped></style>
