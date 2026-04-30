/**
 * Dashboard Download Functions — TDD Tests
 * 測試患者記錄下載邏輯（本地 CSV 和雲端上傳）
 */

describe('Dashboard Download Functions', () => {
  let mockDOM;
  let selectedPatients;
  let allPatients;

  beforeEach(() => {
    // 模擬 DOM 結構
    document.body.innerHTML = `
      <div id="selectedCount"></div>
      <button id="downloadLocalBtn" disabled></button>
      <button id="downloadGoogleBtn" disabled></button>
      <button id="downloadDropboxBtn" disabled></button>
      <button id="downloadS3Btn" disabled></button>
    `;

    // 模擬全局狀態
    selectedPatients = new Set(['P001', 'P002']);
    allPatients = [
      { id: 'P001', name: '王小明', date: '2026-04-24', eye_screen: true },
      { id: 'P002', name: '李美華', date: '2026-04-23', eye_screen: false },
      { id: 'P003', name: '陳浩天', date: '2026-04-22', eye_screen: true },
    ];
  });

  describe('updateDownloadButtonsState()', () => {
    it('should enable all download buttons when patients are selected', () => {
      // 準備：已選擇患者
      selectedPatients.add('P001');

      // 執行
      updateDownloadButtonsState();

      // 驗證：所有下載按鈕應該啟用
      expect(document.getElementById('downloadLocalBtn').disabled).toBe(false);
      expect(document.getElementById('downloadGoogleBtn').disabled).toBe(false);
      expect(document.getElementById('downloadDropboxBtn').disabled).toBe(false);
      expect(document.getElementById('downloadS3Btn').disabled).toBe(false);
    });

    it('should disable all download buttons when no patients are selected', () => {
      // 準備：清除選擇
      selectedPatients.clear();

      // 執行
      updateDownloadButtonsState();

      // 驗證：所有下載按鈕應該禁用
      expect(document.getElementById('downloadLocalBtn').disabled).toBe(true);
      expect(document.getElementById('downloadGoogleBtn').disabled).toBe(true);
      expect(document.getElementById('downloadDropboxBtn').disabled).toBe(true);
      expect(document.getElementById('downloadS3Btn').disabled).toBe(true);
    });
  });

  describe('downloadLocalBtn()', () => {
    it('should generate CSV with selected patients', () => {
      // 準備：模擬 blob 和 link
      const createElementSpy = spyOn(document, 'createElement').and.callThrough();
      const linkClickSpy = jasmine.createSpy('click');

      // 執行
      downloadLocalBtn();

      // 驗證：應該建立並點擊 link
      expect(createElementSpy).toHaveBeenCalledWith('a');
      expect(linkClickSpy).toHaveBeenCalled();
    });

    it('should include selected patients in CSV', () => {
      // 準備：監視 blob 創建
      const blobSpy = spyOn(window, 'Blob').and.callThrough();

      // 執行
      downloadLocalBtn();

      // 驗證：CSV 應該包含患者數據
      const blobCall = blobSpy.calls.mostRecent();
      const csvContent = blobCall.args[0][0];
      expect(csvContent).toContain('王小明');
      expect(csvContent).toContain('李美華');
      expect(csvContent).not.toContain('陳浩天'); // 未選擇
    });

    it('should show alert if no patients selected', () => {
      // 準備
      selectedPatients.clear();
      const alertSpy = spyOn(window, 'alert');

      // 執行
      downloadLocalBtn();

      // 驗證
      expect(alertSpy).toHaveBeenCalledWith('請先選擇患者');
    });
  });

  describe('downloadGoogleBtn()', () => {
    it('should trigger Google Drive OAuth flow', () => {
      // 準備：模擬 window.open
      const openSpy = spyOn(window, 'open').and.returnValue({});

      // 執行
      downloadGoogleBtn();

      // 驗證：應該開啟 OAuth 授權窗口
      expect(openSpy).toHaveBeenCalled();
      const callArgs = openSpy.calls.mostRecent().args[0];
      expect(callArgs).toContain('google');
      expect(callArgs).toContain('oauth');
    });

    it('should show error if Google auth fails', () => {
      // 準備：模擬失敗狀態
      const alertSpy = spyOn(window, 'alert');
      spyOn(window, 'open').and.returnValue(null);

      // 執行
      downloadGoogleBtn();

      // 驗證
      expect(alertSpy).toHaveBeenCalledWith(jasmine.stringContaining('授權失敗'));
    });

    it('should upload CSV to Google Drive on success', async () => {
      // 準備：模擬成功授權
      const fetchSpy = spyOn(window, 'fetch').and.returnValue(
        Promise.resolve(new Response(JSON.stringify({ success: true })))
      );

      // 執行
      await downloadGoogleBtn();

      // 驗證：應該上傳到 Google Drive API
      expect(fetchSpy).toHaveBeenCalled();
      const callArgs = fetchSpy.calls.mostRecent().args;
      expect(callArgs[0]).toContain('googleapis');
    });
  });

  describe('downloadDropboxBtn()', () => {
    it('should trigger Dropbox OAuth flow', () => {
      // 準備
      const openSpy = spyOn(window, 'open').and.returnValue({});

      // 執行
      downloadDropboxBtn();

      // 驗證
      expect(openSpy).toHaveBeenCalled();
      const callArgs = openSpy.calls.mostRecent().args[0];
      expect(callArgs).toContain('dropbox');
    });

    it('should upload CSV to Dropbox on success', async () => {
      // 準備
      const fetchSpy = spyOn(window, 'fetch').and.returnValue(
        Promise.resolve(new Response(JSON.stringify({ success: true })))
      );

      // 執行
      await downloadDropboxBtn();

      // 驗證
      expect(fetchSpy).toHaveBeenCalled();
      const callArgs = fetchSpy.calls.mostRecent().args;
      expect(callArgs[0]).toContain('dropbox');
    });
  });

  describe('downloadS3Btn()', () => {
    it('should get signed URL from backend', async () => {
      // 準備
      const fetchSpy = spyOn(window, 'fetch').and.returnValue(
        Promise.resolve(new Response(JSON.stringify({
          signedUrl: 'https://s3.amazonaws.com/...',
          success: true
        })))
      );

      // 執行
      await downloadS3Btn();

      // 驗證：應該請求簽署 URL
      expect(fetchSpy).toHaveBeenCalled();
      const callArgs = fetchSpy.calls.mostRecent().args;
      expect(callArgs[0]).toContain('/api/v1');
      expect(callArgs[0]).toContain('s3');
    });

    it('should upload CSV to S3 using signed URL', async () => {
      // 準備
      const signedUrl = 'https://s3.amazonaws.com/bucket/file';
      spyOn(window, 'fetch').and.returnValues(
        Promise.resolve(new Response(JSON.stringify({
          signedUrl: signedUrl,
          success: true
        }))),
        Promise.resolve(new Response('', { status: 200 }))
      );

      // 執行
      await downloadS3Btn();

      // 驗證：第二次 fetch 應該上傳到簽署 URL
      const calls = (window.fetch as jasmine.Spy).calls.all();
      expect(calls.length).toBe(2);
      expect(calls[1].args[0]).toBe(signedUrl);
      expect(calls[1].args[1].method).toBe('PUT');
    });
  });
});
