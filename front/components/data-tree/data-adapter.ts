import { TreeData } from './data-tree-context'

// YOLO检测数据接口
export interface YOLODetectionData {
  total_score: number;
  smoothness_score: number;
  width_score: number;
  defect_score: number;
  timestamp: string;
  actual_width?: number;
  defect_type_name?: string;
}

// 将YOLO检测数据转换为数据树格式
export function convertYOLOToTreeData(yoloData: YOLODetectionData): TreeData {
  // 计算最终分数（使用与data-tree-receiver相同的权重）
  const totalWeight = 0.7
  const otherWeight = (1 - totalWeight) / 3
  
  const finalScore = 
    yoloData.total_score * totalWeight +
    yoloData.defect_score * otherWeight +
    yoloData.width_score * otherWeight +
    yoloData.smoothness_score * otherWeight

  return {
    id: `YOLO-${Date.now()}-${Math.random().toString(36).substr(2, 6).toUpperCase()}`,
    time: yoloData.timestamp || new Date().toISOString(),
    defectType: yoloData.defect_type_name || 'None',
    defectScore: yoloData.defect_score,
    widthScore: yoloData.width_score,
    smoothnessScore: yoloData.smoothness_score,
    totalScore: yoloData.total_score,
    finalScore: Math.min(100, Math.max(0, finalScore)) // 限制在0-100之间
  }
}

