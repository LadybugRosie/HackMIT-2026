<template>
  <menus-button
    ico="date"
    :text="t('insert.date')"
    menu-type="dropdown"
    huge
    :select-options="options"
    @click="setDate"
  />
</template>

<script setup>
const formDate = (format) => useDateFormat(useNow(), format).value
const formatDateToChinese = (dateStr) => {
  const replaceDigits = (num) => {
    const digits = ['〇', '一', '二', '三', '四', '五', '六', '七', '八', '九']
    return num
      .toString()
      .split('')
      .map((n) => digits[n])
      .join('')
  }

  return dateStr.replace(/\d+/g, (match) => {
    if (match.length === 4) {
      // 年份
      return replaceDigits(match)
    } else if (match.length === 1) {
      // 月份或日期
      return replaceDigits(match)
    } else if (match.length === 2) {
      const num1 = match.charAt(0)
      const num2 = match.charAt(1)
      if (num1 === '0') {
        return replaceDigits(num1) + '十'
      } else if (num1 === '1') {
        return '十' + replaceDigits(num2)
      } else if (num2 === '0') {
        return replaceDigits(num1) + '十'
      } else {
        return replaceDigits(num1) + '十' + replaceDigits(num2)
      }
    }
    return match // 其他情况不处理
  })
}

const { options: storeOptions } = useStore()
const options = computed(() => {
  const locale = storeOptions.value.locale
  
  switch (locale) {
    case 'zh-CN':
      // Chinese formats
      return [
        { content: formDate('YYYY年M月D日') },
        { content: formDate('YYYY-M-D') },
        { content: formDate('YYYY/M/D') },
        { content: formDate('YYYY.M.D') },
        { content: formDate('YYYY年M月') },
        { content: formDate('YYYY年M月D日 dddd'), divider: true },
        { content: formatDateToChinese(formDate('YYYY年M月D日')) },
        { content: formatDateToChinese(formDate('YYYY年M月')) },
        { content: formatDateToChinese(formDate('YYYY年M月D日 dddd')) },
      ]
    
    case 'ja-JP':
    case 'Ja-ja':
      // Japanese formats
      return [
        { content: formDate('YYYY年M月D日') },
        { content: formDate('YYYY-MM-DD') },
        { content: formDate('YYYY/MM/DD') },
        { content: formDate('M月D日') },
        { content: formDate('YYYY年M月D日(ddd)') },
        { content: formDate('令和YY年M月D日') },
      ]
    
    case 'ar-KSA':
    case 'Ar-KSA':
      // Arabic formats
      return [
        { content: formDate('DD/MM/YYYY') },
        { content: formDate('YYYY-MM-DD') },
        { content: formDate('D-M-YYYY') },
        { content: formDate('DD-MM-YYYY') },
        { content: formDate('YYYY/MM/DD') },
        { content: formDate('D/M/YYYY') },
      ]
    
    case 'sp-SPA':
      // Spanish formats
      return [
        { content: formDate('DD/MM/YYYY') },
        { content: formDate('D/M/YYYY') },
        { content: formDate('DD-MM-YYYY') },
        { content: formDate('YYYY-MM-DD') },
        { content: formDate('DD.MM.YYYY') },
        { content: formDate('D-M-YY') },
      ]
    
    case 'hi-IN':
      // Hindi formats (Indian date formats)
      return [
        { content: formDate('DD/MM/YYYY') },
        { content: formDate('D/M/YYYY') },
        { content: formDate('DD-MM-YYYY') },
        { content: formDate('YYYY-MM-DD') },
        { content: formDate('DD.MM.YYYY') },
        { content: formDate('D-M-YY') },
      ]
    
    case 'ur-IN':
    case 'Ur-Urdu':
      // Urdu formats
      return [
        { content: formDate('DD/MM/YYYY') },
        { content: formDate('D/M/YYYY') },
        { content: formDate('DD-MM-YYYY') },
        { content: formDate('YYYY-MM-DD') },
        { content: formDate('DD.MM.YYYY') },
        { content: formDate('D-M-YY') },
      ]
    
    case 'kn-IN':
    case 'ka-In':
      // Kannada formats
      return [
        { content: formDate('DD/MM/YYYY') },
        { content: formDate('D/M/YYYY') },
        { content: formDate('DD-MM-YYYY') },
        { content: formDate('YYYY-MM-DD') },
        { content: formDate('DD.MM.YYYY') },
        { content: formDate('D-M-YY') },
      ]
    
    case 'ta-IN':
      // Tamil formats
      return [
        { content: formDate('DD/MM/YYYY') },
        { content: formDate('D/M/YYYY') },
        { content: formDate('DD-MM-YYYY') },
        { content: formDate('YYYY-MM-DD') },
        { content: formDate('DD.MM.YYYY') },
        { content: formDate('D-M-YY') },
      ]
    
    case 'te-IN':
      // Telugu formats
      return [
        { content: formDate('DD/MM/YYYY') },
        { content: formDate('D/M/YYYY') },
        { content: formDate('DD-MM-YYYY') },
        { content: formDate('YYYY-MM-DD') },
        { content: formDate('DD.MM.YYYY') },
        { content: formDate('D-M-YY') },
      ]
    
    default:
      // English and other formats (including en-US)
      return [
        { content: formDate('MM/DD/YYYY') },
        { content: formDate('M/D/YYYY') },
        { content: formDate('YYYY-MM-DD') },
        { content: formDate('DD/MM/YYYY') },
        { content: formDate('MM-DD-YYYY') },
        { content: formDate('M-D-YY') },
        { content: formDate('YYYY/MM/DD') },
      ]
  }
})

const { editor } = useStore()

const setDate = ({ content }) => {
  if (!content) {
    return
  }
  editor.value?.chain().focus().insertContent(content).run()
}
</script>
