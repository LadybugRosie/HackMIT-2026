<template>
  <menus-button
    ico="chinese-case"
    :text="t('tools.chineseCase.text')"
    :tooltip="t('tools.chineseCase.tip')"
    menu-type="dropdown"
    huge
    overlay-class-name="chinese-case-dropdown"
  >
    <template #dropmenu>
      <t-dropdown-menu>
        <t-dropdown-item
          v-for="item in options"
          :key="item.value"
          :value="item.value"
          :divider="item.divider"
          @click="setChineseCase(item.func)"
        >
          <div class="label">{{ item.label }}</div>
          <div class="desc">{{ item.desc }}</div>
        </t-dropdown-item>
      </t-dropdown-menu>
    </template>
  </menus-button>
</template>

<script setup>
import nzh from 'nzh/cn'
const { editor } = useStore()

const options = [
  {
    label: t('tools.chineseCase.options.numberToCurrency'),
    desc: t('tools.chineseCase.options.numberToCurrencyDesc'),
    func(text) {
      const number = text
        .toString()
        .replaceAll(',', '')
        .replaceAll('￥', '')
        .replaceAll(' ', '')
      return nzh.toMoney(number, { unOmitYuan: true, forceZheng: true })
    },
  },
  {
    label: t('tools.chineseCase.options.arabicToChinese'),
    desc: t('tools.chineseCase.options.arabicToChineseDesc'),
    func: (text) => nzh.encodeS(text),
  },
  {
    label: t('tools.chineseCase.options.scientificToChinese'),
    desc: t('tools.chineseCase.options.scientificToChineseDesc'),
    func: (text) => nzh.encodeS(text),
    divider: true,
  },
  {
    label: t('tools.chineseCase.options.currencyToNumber'),
    desc: t('tools.chineseCase.options.currencyToNumberDesc'),
    func(text) {
      const char = text
        .replaceAll('人民币', '')
        .replaceAll('元', '')
        .replaceAll('整', '')
      const amount = nzh.decodeB(char).toString()

      // 使用正则表达式添加千位分隔符
      const parts = amount.split('.')
      parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ',')
      // 如果有小数部分，保留两位小数
      if (parts.length === 2) {
        parts[1] = parts[1].padEnd(2, '0')
      } else {
        parts.push('00')
      }
      // 拼接为金额格式的字符串
      const result = parts.join('.')
      return '￥' + result
    },
  },
  {
    label: t('tools.chineseCase.options.chineseToArabic'),
    desc: t('tools.chineseCase.options.chineseToArabicDesc'),
    func: (text) => nzh.decodeS(text),
  },
]

const setChineseCase = (func) => {
  try {
    if (!editor.value) {
      return
    }
    const text = editor.value.commands.getSelectionText()
    if (text === '') {
      return
    }
    const content = func(text)
    if (content === '') {
      throw new Error(t('tools.chineseCase.conversionFailed'))
    } else {
      editor.value.chain().focus().insertContent(content.toString()).run()
    }
  } catch {
    useMessage('error', t('tools.chineseCase.conversionError'))
  }
}
</script>

<style lang="less">
.chinese-case-dropdown {
  .umo-dropdown__item {
    max-width: unset !important;
    &-text {
      padding: 5px;
      .label {
        font-size: 14px;
        color: var(--umo-text-color);
      }
      .desc {
        color: var(--umo-text-color-light);
        margin-top: -3px;
      }
    }
  }
}
</style>
