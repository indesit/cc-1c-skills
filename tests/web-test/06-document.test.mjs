export const name = 'Документ: создание, проведение, проверка в списке';
export const tags = ['document', 'smoke'];
export const timeout = 90000;

export default async function({ navigateSection, openCommand, clickElement, fillFields, fillTableRow, readTable, closeForm, getFormState, assert, step, log }) {

  const docId = `Тест-${Date.now()}`;

  await step('workflow: создать накладную, заполнить, провести и закрыть', async () => {
    await navigateSection('Склад');
    await openCommand('Приходная накладная');
    await clickElement('Создать');

    await fillFields({
      'Контрагент': 'ООО Север',
      'Комментарий': docId,
    });
    await fillTableRow(
      { 'Номенклатура': 'Товар 01', 'Количество': '5', 'Цена': '100' },
      { table: 'Товары', add: true }
    );
    await fillTableRow(
      { 'Номенклатура': 'Товар 02', 'Количество': '3', 'Цена': '200' },
      { table: 'Товары', add: true }
    );

    await clickElement('Провести и закрыть');
    const after = await getFormState();
    const stillOnDoc = !!after.fields?.find(f => f.name === 'Контрагент');
    log(`stillOnDoc=${stillOnDoc} form=${after.form}`);
    assert.ok(!stillOnDoc, 'После Провести и закрыть форма документа должна закрыться (Контрагент-поля нет в текущей форме)');
  });

  await step('verify-list: документ виден в списке с Проведён=Да', async () => {
    await navigateSection('Склад');
    await openCommand('Приходная накладная');
    const t = await readTable({ maxRows: 50 });
    const ours = t.rows.find(r => r['Контрагент'] === 'ООО Север' && r['Проведён'] === 'Да');
    log(`found posted: ${JSON.stringify(ours)}`);
    assert.ok(ours, 'Должен быть проведённый документ ООО Север');
    await closeForm();
  });
}
