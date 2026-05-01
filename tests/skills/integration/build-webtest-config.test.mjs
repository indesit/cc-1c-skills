// build-webtest-config.test.mjs — Integration test: build synthetic configuration for web-test regression
// Extends base-config with: diverse field types, hierarchical catalog, two-tab form,
// second subsystem, full-rights role.
// Steps: cf-init → meta-compile → form-add + form-compile → skd-compile
//        → subsystem-compile → role-compile → cf-edit → cf-validate

export const name = 'Сборка конфигурации для web-test';
export const setup = 'none';
export const cache = 'webtest-config';

export const steps = [
  // ── 1. Init empty configuration ──
  {
    name: 'cf-init: пустая конфигурация',
    script: 'cf-init/scripts/cf-init',
    args: { '-Name': 'ТестоваяВебКонфигурация', '-OutputDir': '{workDir}' },
    validate: { script: 'cf-validate/scripts/cf-validate', flag: '-ConfigPath' },
  },

  // ── 2. Metadata objects ──

  // Справочник Контрагенты — простой, для CRUD и ссылочных полей
  {
    name: 'meta-compile: Справочник Контрагенты',
    script: 'meta-compile/scripts/meta-compile',
    input: {
      type: 'Catalog', name: 'Контрагенты',
      codeLength: 9, descriptionLength: 100,
      attributes: [
        { name: 'ИНН', type: 'String', length: 12 },
        { name: 'Телефон', type: 'String', length: 20 },
        { name: 'Адрес', type: 'String', length: 200 },
        { name: 'КодКПП', type: 'String', length: 9 },
      ],
    },
    args: { '-JsonPath': '{inputFile}', '-OutputDir': '{workDir}' },
    validate: { script: 'meta-validate/scripts/meta-validate', flag: '-ObjectPath', path: 'Catalogs/Контрагенты' },
  },

  // Подчинённый каталог КонтактныеЛица — для теста getFormState.navigation (subordinate-nav)
  {
    name: 'meta-compile: Справочник КонтактныеЛица (подчинённый Контрагентам)',
    script: 'meta-compile/scripts/meta-compile',
    input: {
      type: 'Catalog', name: 'КонтактныеЛица',
      codeLength: 9, descriptionLength: 100,
      owners: ['Catalog.Контрагенты'],
      attributes: [
        { name: 'Должность', type: 'String', length: 100 },
        { name: 'Телефон', type: 'String', length: 20 },
      ],
    },
    args: { '-JsonPath': '{inputFile}', '-OutputDir': '{workDir}' },
    validate: { script: 'meta-validate/scripts/meta-validate', flag: '-ObjectPath', path: 'Catalogs/КонтактныеЛица' },
  },

  // Справочник Номенклатура — иерархический, все типы полей
  {
    name: 'meta-compile: Справочник Номенклатура',
    script: 'meta-compile/scripts/meta-compile',
    input: {
      type: 'Catalog', name: 'Номенклатура',
      codeLength: 11, descriptionLength: 150,
      hierarchical: true,
      attributes: [
        { name: 'Артикул', type: 'String', length: 25 },
        { name: 'Цена', type: 'Number', length: 15, precision: 2 },
        { name: 'Активен', type: 'Boolean' },
        { name: 'ДатаПоступления', type: 'Date' },
        { name: 'Комментарий', type: 'String' },
        { name: 'ЕдиницаИзмерения', type: 'String', length: 10 },
        { name: 'ВидНоменклатуры', type: 'EnumRef.ВидыНоменклатуры' },
        { name: 'КатегорияЦены', type: 'EnumRef.КатегорииЦен' },
      ],
      fillChecking: { 'Description': 'ShowError' },
    },
    args: { '-JsonPath': '{inputFile}', '-OutputDir': '{workDir}' },
    validate: { script: 'meta-validate/scripts/meta-validate', flag: '-ObjectPath', path: 'Catalogs/Номенклатура' },
  },

  // Перечисление ВидыНоменклатуры
  {
    name: 'meta-compile: Перечисление ВидыНоменклатуры',
    script: 'meta-compile/scripts/meta-compile',
    input: {
      type: 'Enum', name: 'ВидыНоменклатуры',
      values: ['Товар', 'Услуга', 'Работа'],
    },
    args: { '-JsonPath': '{inputFile}', '-OutputDir': '{workDir}' },
    validate: { script: 'meta-validate/scripts/meta-validate', flag: '-ObjectPath', path: 'Enums/ВидыНоменклатуры' },
  },

  // Перечисление КатегорииЦен — для будущего radio-button теста (fillFields branch #3)
  {
    name: 'meta-compile: Перечисление КатегорииЦен',
    script: 'meta-compile/scripts/meta-compile',
    input: {
      type: 'Enum', name: 'КатегорииЦен',
      values: ['Розничная', 'Оптовая', 'Закупочная'],
    },
    args: { '-JsonPath': '{inputFile}', '-OutputDir': '{workDir}' },
    validate: { script: 'meta-validate/scripts/meta-validate', flag: '-ObjectPath', path: 'Enums/КатегорииЦен' },
  },

  // Документ ПриходнаяНакладная — шапка + ТЧ
  {
    name: 'meta-compile: Документ ПриходнаяНакладная',
    script: 'meta-compile/scripts/meta-compile',
    input: {
      type: 'Document', name: 'ПриходнаяНакладная',
      attributes: [
        { name: 'Контрагент', type: 'CatalogRef.Контрагенты' },
        { name: 'Склад', type: 'String', length: 50 },
        { name: 'Комментарий', type: 'String', length: 200 },
      ],
      tabularSections: [{
        name: 'Товары',
        attributes: [
          { name: 'Номенклатура', type: 'CatalogRef.Номенклатура' },
          { name: 'Количество', type: 'Number', length: 15, precision: 3 },
          { name: 'Цена', type: 'Number', length: 15, precision: 2 },
          { name: 'Сумма', type: 'Number', length: 15, precision: 2 },
          { name: 'Согласовано', type: 'Boolean' },
        ],
      }],
    },
    args: { '-JsonPath': '{inputFile}', '-OutputDir': '{workDir}' },
    validate: { script: 'meta-validate/scripts/meta-validate', flag: '-ObjectPath', path: 'Documents/ПриходнаяНакладная' },
  },

  // Регистр сведений КурсыВалют (Independent — без регистратора)
  {
    name: 'meta-compile: Регистр сведений КурсыВалют',
    script: 'meta-compile/scripts/meta-compile',
    input: {
      type: 'InformationRegister', name: 'КурсыВалют',
      writeMode: 'Independent',
      dimensions: [
        { name: 'Валюта', type: 'String', length: 10 },
      ],
      resources: [
        { name: 'Курс', type: 'Number', length: 10, precision: 4 },
        { name: 'Кратность', type: 'Number', length: 10 },
      ],
    },
    args: { '-JsonPath': '{inputFile}', '-OutputDir': '{workDir}' },
    validate: { script: 'meta-validate/scripts/meta-validate', flag: '-ObjectPath', path: 'InformationRegisters/КурсыВалют' },
  },

  // Константа ОсновнаяВалюта
  {
    name: 'meta-compile: Константа ОсновнаяВалюта',
    script: 'meta-compile/scripts/meta-compile',
    input: {
      type: 'Constant', name: 'ОсновнаяВалюта',
      valueType: 'String', length: 10,
    },
    args: { '-JsonPath': '{inputFile}', '-OutputDir': '{workDir}' },
    validate: { script: 'meta-validate/scripts/meta-validate', flag: '-ObjectPath', path: 'Constants/ОсновнаяВалюта' },
  },

  // Общий модуль ОбщиеФункции
  {
    name: 'meta-compile: Общий модуль ОбщиеФункции',
    script: 'meta-compile/scripts/meta-compile',
    input: {
      type: 'CommonModule', name: 'ОбщиеФункции',
      server: true, clientManagedApplication: false,
    },
    args: { '-JsonPath': '{inputFile}', '-OutputDir': '{workDir}' },
    validate: { script: 'meta-validate/scripts/meta-validate', flag: '-ObjectPath', path: 'CommonModules/ОбщиеФункции' },
  },
  {
    name: 'writeFile: ОбщиеФункции Module.bsl',
    writeFile: 'CommonModules/ОбщиеФункции/Ext/Module.bsl',
    content: `Процедура ПоказатьСообщение() Экспорт
\tСообщить("Тестовое сообщение");
КонецПроцедуры

Процедура ВызватьТестовоеИсключение() Экспорт
\tВызватьИсключение "Тестовое исключение";
КонецПроцедуры
`,
  },

  // Обработка ТестовыеОшибки — для тестов errors balloon/messages/modal (10-validation)
  {
    name: 'meta-compile: Обработка ТестовыеОшибки',
    script: 'meta-compile/scripts/meta-compile',
    input: {
      type: 'DataProcessor', name: 'ТестовыеОшибки',
    },
    args: { '-JsonPath': '{inputFile}', '-OutputDir': '{workDir}' },
    validate: { script: 'meta-validate/scripts/meta-validate', flag: '-ObjectPath', path: 'DataProcessors/ТестовыеОшибки' },
  },

  // Отчёт ОстаткиТоваров
  {
    name: 'meta-compile: Отчёт ОстаткиТоваров',
    script: 'meta-compile/scripts/meta-compile',
    input: {
      type: 'Report', name: 'ОстаткиТоваров',
    },
    args: { '-JsonPath': '{inputFile}', '-OutputDir': '{workDir}' },
    validate: { script: 'meta-validate/scripts/meta-validate', flag: '-ObjectPath', path: 'Reports/ОстаткиТоваров' },
  },

  // ── 3. Forms ──

  // Форма элемента Контрагенты — простая
  {
    name: 'form-add: Форма элемента Контрагенты',
    script: 'form-add/scripts/form-add',
    args: { '-ObjectPath': '{workDir}/Catalogs/Контрагенты.xml', '-FormName': 'ФормаЭлемента' },
  },
  {
    name: 'form-compile: Форма элемента Контрагенты',
    script: 'form-compile/scripts/form-compile',
    input: {
      title: 'Контрагент',
      attributes: [
        { name: 'Объект', type: 'CatalogObject.Контрагенты', main: true },
      ],
      elements: [
        { input: 'Наименование', path: 'Объект.Description', title: 'Наименование' },
        { input: 'ИНН', path: 'Объект.ИНН', title: 'ИНН' },
        { input: 'Телефон', path: 'Объект.Телефон', title: 'Телефон' },
        { input: 'Адрес', path: 'Объект.Адрес', title: 'Адрес' },
      ],
    },
    args: { '-JsonPath': '{inputFile}', '-OutputPath': '{workDir}/Catalogs/Контрагенты/Forms/ФормаЭлемента/Ext/Form.xml' },
    validate: { script: 'form-validate/scripts/form-validate', flag: '-FormPath', path: 'Catalogs/Контрагенты/Forms/ФормаЭлемента/Ext/Form.xml' },
  },

  // Форма элемента КонтактныеЛица + список — для подчинённого каталога
  {
    name: 'form-add: Форма элемента КонтактныеЛица',
    script: 'form-add/scripts/form-add',
    args: { '-ObjectPath': '{workDir}/Catalogs/КонтактныеЛица.xml', '-FormName': 'ФормаЭлемента' },
  },
  {
    name: 'form-compile: Форма элемента КонтактныеЛица',
    script: 'form-compile/scripts/form-compile',
    input: {
      title: 'Контактное лицо',
      attributes: [
        { name: 'Объект', type: 'CatalogObject.КонтактныеЛица', main: true },
      ],
      elements: [
        { input: 'Владелец', path: 'Объект.Owner', title: 'Контрагент' },
        { input: 'Наименование', path: 'Объект.Description', title: 'ФИО' },
        { input: 'Должность', path: 'Объект.Должность', title: 'Должность' },
        { input: 'Телефон', path: 'Объект.Телефон', title: 'Телефон' },
      ],
    },
    args: { '-JsonPath': '{inputFile}', '-OutputPath': '{workDir}/Catalogs/КонтактныеЛица/Forms/ФормаЭлемента/Ext/Form.xml' },
    validate: { script: 'form-validate/scripts/form-validate', flag: '-FormPath', path: 'Catalogs/КонтактныеЛица/Forms/ФормаЭлемента/Ext/Form.xml' },
  },
  {
    name: 'form-add: Форма списка КонтактныеЛица',
    script: 'form-add/scripts/form-add',
    args: { '-ObjectPath': '{workDir}/Catalogs/КонтактныеЛица.xml', '-FormName': 'ФормаСписка', '-Purpose': 'List' },
  },
  {
    name: 'form-compile: Форма списка КонтактныеЛица',
    script: 'form-compile/scripts/form-compile',
    input: {
      title: 'Контактные лица',
      attributes: [
        { name: 'Список', type: 'DynamicList', main: true,
          settings: { mainTable: 'Catalog.КонтактныеЛица', dynamicDataRead: true } },
      ],
      elements: [
        { table: 'Список', path: 'Список', columns: [
          { input: 'Description', path: 'Список.Description', title: 'ФИО' },
          { input: 'Должность', path: 'Список.Должность', title: 'Должность' },
          { input: 'Телефон', path: 'Список.Телефон', title: 'Телефон' },
        ]},
      ],
    },
    args: { '-JsonPath': '{inputFile}', '-OutputPath': '{workDir}/Catalogs/КонтактныеЛица/Forms/ФормаСписка/Ext/Form.xml' },
    validate: { script: 'form-validate/scripts/form-validate', flag: '-FormPath', path: 'Catalogs/КонтактныеЛица/Forms/ФормаСписка/Ext/Form.xml' },
  },

  // Форма списка Контрагенты — для filterList тестов. КодКПП НЕ выводим
  // в форму — это покрывает FieldSelector DLB ветку (filterList #5)
  {
    name: 'form-add: Форма списка Контрагенты',
    script: 'form-add/scripts/form-add',
    args: { '-ObjectPath': '{workDir}/Catalogs/Контрагенты.xml', '-FormName': 'ФормаСписка', '-Purpose': 'List' },
  },
  {
    name: 'form-compile: Форма списка Контрагенты',
    script: 'form-compile/scripts/form-compile',
    input: {
      title: 'Контрагенты',
      attributes: [
        { name: 'Список', type: 'DynamicList', main: true,
          settings: { mainTable: 'Catalog.Контрагенты', dynamicDataRead: true } },
      ],
      elements: [
        { table: 'Список', path: 'Список', columns: [
          { input: 'Code', path: 'Список.Code', title: 'Код' },
          { input: 'Description', path: 'Список.Description', title: 'Наименование' },
          { input: 'ИНН', path: 'Список.ИНН', title: 'ИНН' },
          { input: 'Телефон', path: 'Список.Телефон', title: 'Телефон' },
          { input: 'Адрес', path: 'Список.Адрес', title: 'Адрес' },
        ]},
      ],
    },
    args: { '-JsonPath': '{inputFile}', '-OutputPath': '{workDir}/Catalogs/Контрагенты/Forms/ФормаСписка/Ext/Form.xml' },
    validate: { script: 'form-validate/scripts/form-validate', flag: '-FormPath', path: 'Catalogs/Контрагенты/Forms/ФормаСписка/Ext/Form.xml' },
  },

  // Форма элемента Номенклатура — 2 вкладки, все типы полей
  {
    name: 'form-add: Форма элемента Номенклатура',
    script: 'form-add/scripts/form-add',
    args: { '-ObjectPath': '{workDir}/Catalogs/Номенклатура.xml', '-FormName': 'ФормаЭлемента' },
  },
  {
    name: 'form-compile: Форма элемента Номенклатура (2 вкладки)',
    script: 'form-compile/scripts/form-compile',
    input: {
      title: 'Номенклатура',
      attributes: [
        { name: 'Объект', type: 'CatalogObject.Номенклатура', main: true },
      ],
      elements: [
        { pages: 'Страницы', children: [
          { page: 'Основное', children: [
            { input: 'Наименование', path: 'Объект.Description', title: 'Наименование' },
            { input: 'Артикул', path: 'Объект.Артикул', title: 'Артикул' },
            { input: 'ВидНоменклатуры', path: 'Объект.ВидНоменклатуры', title: 'Вид номенклатуры' },
            { input: 'Цена', path: 'Объект.Цена', title: 'Цена' },
            { input: 'КатегорияЦены', path: 'Объект.КатегорияЦены', title: 'Категория цены' },
            { input: 'Активен', path: 'Объект.Активен', title: 'Активен' },
            { input: 'ДатаПоступления', path: 'Объект.ДатаПоступления', title: 'Дата поступления' },
          ]},
          { page: 'Дополнительно', children: [
            { input: 'ЕдиницаИзмерения', path: 'Объект.ЕдиницаИзмерения', title: 'Единица измерения' },
            { input: 'Комментарий', path: 'Объект.Комментарий', title: 'Комментарий' },
          ]},
        ]},
      ],
    },
    args: { '-JsonPath': '{inputFile}', '-OutputPath': '{workDir}/Catalogs/Номенклатура/Forms/ФормаЭлемента/Ext/Form.xml' },
    validate: { script: 'form-validate/scripts/form-validate', flag: '-FormPath', path: 'Catalogs/Номенклатура/Forms/ФормаЭлемента/Ext/Form.xml' },
  },

  // Форма списка Номенклатура — с колонкой ДатаПоступления для filterList #6 (date pattern)
  {
    name: 'form-add: Форма списка Номенклатура',
    script: 'form-add/scripts/form-add',
    args: { '-ObjectPath': '{workDir}/Catalogs/Номенклатура.xml', '-FormName': 'ФормаСписка', '-Purpose': 'List' },
  },
  {
    name: 'form-compile: Форма списка Номенклатура',
    script: 'form-compile/scripts/form-compile',
    input: {
      title: 'Номенклатура',
      attributes: [
        { name: 'Список', type: 'DynamicList', main: true,
          settings: { mainTable: 'Catalog.Номенклатура', dynamicDataRead: true } },
      ],
      elements: [
        { table: 'Список', path: 'Список', columns: [
          { input: 'Code', path: 'Список.Code', title: 'Код' },
          { input: 'Description', path: 'Список.Description', title: 'Наименование' },
          { input: 'Артикул', path: 'Список.Артикул', title: 'Артикул' },
          { input: 'ВидНоменклатуры', path: 'Список.ВидНоменклатуры', title: 'Вид номенклатуры' },
          { input: 'ДатаПоступления', path: 'Список.ДатаПоступления', title: 'Дата поступления' },
          { input: 'Цена', path: 'Список.Цена', title: 'Цена' },
          { input: 'Активен', path: 'Список.Активен', title: 'Активен' },
        ]},
      ],
    },
    args: { '-JsonPath': '{inputFile}', '-OutputPath': '{workDir}/Catalogs/Номенклатура/Forms/ФормаСписка/Ext/Form.xml' },
    validate: { script: 'form-validate/scripts/form-validate', flag: '-FormPath', path: 'Catalogs/Номенклатура/Forms/ФормаСписка/Ext/Form.xml' },
  },

  // Форма документа ПриходнаяНакладная
  {
    name: 'form-add: Форма документа ПриходнаяНакладная',
    script: 'form-add/scripts/form-add',
    args: { '-ObjectPath': '{workDir}/Documents/ПриходнаяНакладная.xml', '-FormName': 'ФормаДокумента' },
  },
  {
    name: 'form-compile: Форма документа ПриходнаяНакладная',
    script: 'form-compile/scripts/form-compile',
    input: {
      title: 'Приходная накладная',
      attributes: [
        { name: 'Объект', type: 'DocumentObject.ПриходнаяНакладная', main: true },
      ],
      elements: [
        { input: 'Контрагент', path: 'Объект.Контрагент', title: 'Контрагент' },
        { input: 'Склад', path: 'Объект.Склад', title: 'Склад' },
        { input: 'Комментарий', path: 'Объект.Комментарий', title: 'Комментарий' },
        { table: 'Товары', path: 'Объект.Товары', title: 'Товары', changeRowSet: true, columns: [
          { input: 'Номенклатура', path: 'Объект.Товары.Номенклатура', title: 'Номенклатура' },
          { input: 'Количество', path: 'Объект.Товары.Количество', title: 'Количество' },
          { input: 'Цена', path: 'Объект.Товары.Цена', title: 'Цена' },
          { input: 'Сумма', path: 'Объект.Товары.Сумма', title: 'Сумма' },
          { check: 'Согласовано', path: 'Объект.Товары.Согласовано', title: 'Согласовано' },
        ]},
      ],
    },
    args: { '-JsonPath': '{inputFile}', '-OutputPath': '{workDir}/Documents/ПриходнаяНакладная/Forms/ФормаДокумента/Ext/Form.xml' },
    validate: { script: 'form-validate/scripts/form-validate', flag: '-FormPath', path: 'Documents/ПриходнаяНакладная/Forms/ФормаДокумента/Ext/Form.xml' },
  },

  // Форма списка ПриходнаяНакладная — с колонкой Контрагент для filterList #7 (reference pattern)
  {
    name: 'form-add: Форма списка ПриходнаяНакладная',
    script: 'form-add/scripts/form-add',
    args: { '-ObjectPath': '{workDir}/Documents/ПриходнаяНакладная.xml', '-FormName': 'ФормаСписка', '-Purpose': 'List' },
  },
  {
    name: 'form-compile: Форма списка ПриходнаяНакладная',
    script: 'form-compile/scripts/form-compile',
    input: {
      title: 'Приходные накладные',
      attributes: [
        { name: 'Список', type: 'DynamicList', main: true,
          settings: { mainTable: 'Document.ПриходнаяНакладная', dynamicDataRead: true } },
      ],
      elements: [
        { table: 'Список', path: 'Список', columns: [
          { input: 'Date', path: 'Список.Date', title: 'Дата' },
          { input: 'Number', path: 'Список.Number', title: 'Номер' },
          { input: 'Контрагент', path: 'Список.Контрагент', title: 'Контрагент' },
          { input: 'Posted', path: 'Список.Posted', title: 'Проведён' },
        ]},
      ],
    },
    args: { '-JsonPath': '{inputFile}', '-OutputPath': '{workDir}/Documents/ПриходнаяНакладная/Forms/ФормаСписка/Ext/Form.xml' },
    validate: { script: 'form-validate/scripts/form-validate', flag: '-FormPath', path: 'Documents/ПриходнаяНакладная/Forms/ФормаСписка/Ext/Form.xml' },
  },

  // Форма обработки ТестовыеОшибки — кнопки вызова процедур ОбщиеФункции
  {
    name: 'form-add: Форма обработки ТестовыеОшибки',
    script: 'form-add/scripts/form-add',
    args: { '-ObjectPath': '{workDir}/DataProcessors/ТестовыеОшибки.xml', '-FormName': 'ФормаОбработки' },
  },
  {
    name: 'form-compile: Форма обработки ТестовыеОшибки',
    script: 'form-compile/scripts/form-compile',
    input: {
      title: 'Тестовые ошибки',
      attributes: [
        { name: 'Объект', type: 'DataProcessorObject.ТестовыеОшибки', main: true },
      ],
      elements: [
        { button: 'ПоказатьСообщение', command: 'ПоказатьСообщение', title: 'Показать сообщение' },
        { button: 'ВызватьИсключение', command: 'ВызватьИсключениеКоманда', title: 'Вызвать исключение' },
      ],
      commands: [
        { name: 'ПоказатьСообщение', action: 'ПоказатьСообщение' },
        { name: 'ВызватьИсключениеКоманда', action: 'ВызватьИсключениеКоманда' },
      ],
    },
    args: { '-JsonPath': '{inputFile}', '-OutputPath': '{workDir}/DataProcessors/ТестовыеОшибки/Forms/ФормаОбработки/Ext/Form.xml' },
    validate: { script: 'form-validate/scripts/form-validate', flag: '-FormPath', path: 'DataProcessors/ТестовыеОшибки/Forms/ФормаОбработки/Ext/Form.xml' },
  },
  {
    name: 'writeFile: ТестовыеОшибки form Module.bsl',
    writeFile: 'DataProcessors/ТестовыеОшибки/Forms/ФормаОбработки/Ext/Form/Module.bsl',
    content: `&НаКлиенте
Процедура ПоказатьСообщение(Команда)
\tПоказатьСообщениеНаСервере();
КонецПроцедуры

&НаСервере
Процедура ПоказатьСообщениеНаСервере()
\tОбщиеФункции.ПоказатьСообщение();
КонецПроцедуры

&НаКлиенте
Процедура ВызватьИсключениеКоманда(Команда)
\tВызватьИсключениеНаСервере();
КонецПроцедуры

&НаСервере
Процедура ВызватьИсключениеНаСервере()
\tОбщиеФункции.ВызватьТестовоеИсключение();
КонецПроцедуры
`,
  },

  // ── 4. DCS for report ──
  {
    name: 'skd-compile: Схема отчёта ОстаткиТоваров',
    script: 'skd-compile/scripts/skd-compile',
    input: {
      dataSets: [{
        name: 'НаборДанных',
        type: 'Query',
        query: 'SELECT Номенклатура, Количество, Цена, Сумма FROM Document.ПриходнаяНакладная.Товары',
      }],
      fields: [
        { name: 'Номенклатура', title: 'Номенклатура' },
        { name: 'Количество', title: 'Количество' },
        { name: 'Цена', title: 'Цена' },
        { name: 'Сумма', title: 'Сумма' },
      ],
    },
    args: { '-DefinitionFile': '{inputFile}', '-OutputPath': '{workDir}/Reports/ОстаткиТоваров/Templates/ОсновнаяСхемаКомпоновкиДанных/Ext/Template.xml' },
    validate: { script: 'skd-validate/scripts/skd-validate', flag: '-TemplatePath', path: 'Reports/ОстаткиТоваров/Templates/ОсновнаяСхемаКомпоновкиДанных/Ext/Template.xml' },
  },

  // ── 5. Subsystems ──
  {
    name: 'subsystem-compile: Подсистема Склад',
    script: 'subsystem-compile/scripts/subsystem-compile',
    input: {
      name: 'Склад',
      synonym: 'Склад',
      content: [
        'Catalog.Контрагенты',
        'Catalog.КонтактныеЛица',
        'Catalog.Номенклатура',
        'Enum.ВидыНоменклатуры',
        'Enum.КатегорииЦен',
        'Document.ПриходнаяНакладная',
        'Report.ОстаткиТоваров',
      ],
    },
    args: { '-DefinitionFile': '{inputFile}', '-OutputDir': '{workDir}' },
    validate: { script: 'subsystem-validate/scripts/subsystem-validate', flag: '-SubsystemPath', path: 'Subsystems/Склад' },
  },
  {
    name: 'subsystem-compile: Подсистема Администрирование',
    script: 'subsystem-compile/scripts/subsystem-compile',
    input: {
      name: 'Администрирование',
      synonym: 'Администрирование',
      content: [
        'InformationRegister.КурсыВалют',
        'Constant.ОсновнаяВалюта',
        'DataProcessor.ТестовыеОшибки',
      ],
    },
    args: { '-DefinitionFile': '{inputFile}', '-OutputDir': '{workDir}' },
    validate: { script: 'subsystem-validate/scripts/subsystem-validate', flag: '-SubsystemPath', path: 'Subsystems/Администрирование' },
  },

  // ── 6. Role with full rights ──
  {
    name: 'role-compile: Роль Администратор',
    script: 'role-compile/scripts/role-compile',
    input: {
      name: 'Администратор',
      objects: [
        'Catalog.Контрагенты: Read View Add Update Delete',
        'Catalog.КонтактныеЛица: Read View Add Update Delete',
        'Catalog.Номенклатура: Read View Add Update Delete',
        'Document.ПриходнаяНакладная: Read View Add Update Delete Posting UnPosting',
        'InformationRegister.КурсыВалют: Read View Add Update Delete',
        'Report.ОстаткиТоваров: Use View',
      ],
    },
    args: { '-JsonPath': '{inputFile}', '-OutputDir': '{workDir}' },
    validate: { script: 'role-validate/scripts/role-validate', flag: '-RightsPath', path: 'Roles/Администратор' },
  },

  // ── 7. Register all objects in Configuration.xml ──
  {
    name: 'cf-edit: Регистрация объектов в конфигурации',
    script: 'cf-edit/scripts/cf-edit',
    input: [
      { operation: 'add-childObject', value: 'Catalog.Контрагенты' },
      { operation: 'add-childObject', value: 'Catalog.КонтактныеЛица' },
      { operation: 'add-childObject', value: 'Catalog.Номенклатура' },
      { operation: 'add-childObject', value: 'Enum.ВидыНоменклатуры' },
      { operation: 'add-childObject', value: 'Enum.КатегорииЦен' },
      { operation: 'add-childObject', value: 'Document.ПриходнаяНакладная' },
      { operation: 'add-childObject', value: 'InformationRegister.КурсыВалют' },
      { operation: 'add-childObject', value: 'Constant.ОсновнаяВалюта' },
      { operation: 'add-childObject', value: 'CommonModule.ОбщиеФункции' },
      { operation: 'add-childObject', value: 'DataProcessor.ТестовыеОшибки' },
      { operation: 'add-childObject', value: 'Report.ОстаткиТоваров' },
      { operation: 'add-childObject', value: 'Subsystem.Склад' },
      { operation: 'add-childObject', value: 'Subsystem.Администрирование' },
      { operation: 'add-childObject', value: 'Role.Администратор' },
    ],
    args: { '-ConfigPath': '{workDir}', '-DefinitionFile': '{inputFile}' },
  },

  // ── 8. Final validation ──
  {
    name: 'cf-validate: Финальная валидация конфигурации',
    script: 'cf-validate/scripts/cf-validate',
    args: { '-ConfigPath': '{workDir}' },
  },
];
