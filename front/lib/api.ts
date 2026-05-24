// API配置 - 统一管理API地址
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const API_ENDPOINTS = {
  // YOLO检测
  START_YOLO: `${API_BASE_URL}/api/v1/start-yolo`,
  STOP_YOLO: `${API_BASE_URL}/api/v1/stop-yolo`,
  YOLO_DATA: `${API_BASE_URL}/api/v1/yolo-data`,
  VIDEO_STREAM: `${API_BASE_URL}/api/v1/video-stream`,
  DETECT: `${API_BASE_URL}/api/v1/detect`,
  DETECT_IMAGE: `${API_BASE_URL}/api/v1/detect-image`,
  SAVE_SCORE: `${API_BASE_URL}/api/v1/save-score`,
  RECENT_SCORES: `${API_BASE_URL}/api/v1/recent-scores`,

  // AI教师
  TEACHER_CHAT: `${API_BASE_URL}/api/v1/teacher/chat`,
  TEACHER_HISTORY: `${API_BASE_URL}/api/v1/teacher/history`,

  // 预测
  PREDICT: `${API_BASE_URL}/api/v1/predict`,
  PREDICT_YOLO_DATA: `${API_BASE_URL}/api/v1/predict/yolo-data`,
  PREDICT_QUALITY: `${API_BASE_URL}/api/v1/predict/quality`,
  PREDICT_AI_ANALYSIS: `${API_BASE_URL}/api/v1/predict/ai-analysis`,
  PREDICT_AI_ANALYSIS_CUSTOM: `${API_BASE_URL}/api/v1/predict/ai-analysis-custom`,
  PREDICT_AI_RADAR: `${API_BASE_URL}/api/v1/predict/ai-radar-data`,

  // 仪表板
  DASHBOARD_STATS: `${API_BASE_URL}/api/v1/dashboard/stats`,
  DASHBOARD_CHARTS: `${API_BASE_URL}/api/v1/dashboard/charts`,
  DASHBOARD_SYSTEM_STATUS: `${API_BASE_URL}/api/v1/dashboard/system-status`,
  DASHBOARD_QUICK_STATS: `${API_BASE_URL}/api/v1/dashboard/quick-stats`,
  DASHBOARD_HISTORY: `${API_BASE_URL}/api/v1/dashboard/history`,

  // 课程计划
  LESSON_PLAN: `${API_BASE_URL}/api/v1/lesson-plan`,
  LESSON_PLAN_PDF: `${API_BASE_URL}/api/v1/lesson-plan/generate-pdf`,
  LESSON_PLAN_PDF_DATA: `${API_BASE_URL}/api/v1/lesson-plan/pdf-data`,

  // PDF异步生成
  PDF_STATUS: (taskId: string) => `${API_BASE_URL}/api/v1/lesson-plan/pdf-status/${taskId}`,
  PDF_DOWNLOAD: (taskId: string) => `${API_BASE_URL}/api/v1/lesson-plan/pdf-download/${taskId}`,

  // 学生比较
  STUDENT_COMPARISON: `${API_BASE_URL}/api/v1/student-comparison`,
  BATCH_LIST: `${API_BASE_URL}/api/v1/batch-list`,

  // 登录
  AUTH_LOGIN: `${API_BASE_URL}/api/v1/auth/login`,

  // 视频上传 (3DGS)
  UPLOAD_VIDEO: `${API_BASE_URL}/api/v1/upload-video`,

  // 3DGS 模型
  MODEL_3DGS: `${API_BASE_URL}/static/3dgs/model_light.ply`,
};

export default API_BASE_URL;
