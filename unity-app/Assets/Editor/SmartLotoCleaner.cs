#if UNITY_EDITOR
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace SmartLOTO.EditorTools
{
    public static class SmartLotoCleaner
    {
        [MenuItem("SmartLOTO/1-Click Scene & Asset Cleaner", false, 100)]
        public static void RunFullCleanup()
        {
            Debug.Log("<color=#5EEAD4><b>[SmartLOTO Cleaner]</b> Démarrage de l'audit et du nettoyage 1-clic...</color>");

            int disabledPanelsCount = CleanLegacySceneObjects();
            int unusedAssetsCount = AuditUnusedAssets();

            EditorUtility.DisplayDialog(
                "SmartLOTO Cleaner Terminé",
                $"Nettoyage & Audit réussis !\n\n" +
                $"• Objets / Panneaux legacy sécurisés/désactivés : {disabledPanelsCount}\n" +
                $"• Fichiers non référencés identifiés : {unusedAssetsCount}\n\n" +
                "Consultez la Console Unity pour la liste détaillée des dépendances.",
                "OK"
            );
        }

        [MenuItem("SmartLOTO/Nettoyer la Scène Active", false, 101)]
        public static int CleanLegacySceneObjects()
        {
            var activeScene = SceneManager.GetActiveScene();
            if (!activeScene.isLoaded)
            {
                Debug.LogWarning("[SmartLOTO Cleaner] Aucune scène active chargée.");
                return 0;
            }

            var uiControllers = Object.FindObjectsByType<LotoUIController>(FindObjectsSortMode.None);
            var managers = Object.FindObjectsByType<LotoManager>(FindObjectsSortMode.None);

            var referencedObjects = new HashSet<GameObject>();

            // 1. Recueillir toutes les références sérialisées de LotoUIController
            foreach (var controller in uiControllers)
            {
                var so = new SerializedObject(controller);
                var prop = so.GetIterator();
                while (prop.NextVisible(true))
                {
                    if (prop.propertyType == SerializedPropertyType.ObjectReference && prop.objectReferenceValue != null)
                    {
                        if (prop.objectReferenceValue is GameObject go) referencedObjects.Add(go);
                        else if (prop.objectReferenceValue is Component comp) referencedObjects.Add(comp.gameObject);
                    }
                }
            }

            // 2. Recueillir toutes les références sérialisées de LotoManager
            foreach (var mgr in managers)
            {
                var so = new SerializedObject(mgr);
                var prop = so.GetIterator();
                while (prop.NextVisible(true))
                {
                    if (prop.propertyType == SerializedPropertyType.ObjectReference && prop.objectReferenceValue != null)
                    {
                        if (prop.objectReferenceValue is GameObject go) referencedObjects.Add(go);
                        else if (prop.objectReferenceValue is Component comp) referencedObjects.Add(comp.gameObject);
                    }
                }
            }

            int processedCount = 0;
            var rootObjects = activeScene.GetRootGameObjects();

            Undo.IncrementCurrentGroup();
            Undo.SetCurrentGroupName("SmartLOTO Safe Scene Clean");
            int undoGroup = Undo.GetCurrentGroup();

            foreach (var root in rootObjects)
            {
                // Ne jamais toucher au HUD généré dynamiquement à l'exécution
                if (root.name.Contains("SmartLoto · Operator HUD") || root.name.Contains("SmartLoto EventSystem"))
                    continue;

                var transforms = root.GetComponentsInChildren<Transform>(true);
                foreach (var t in transforms)
                {
                    var go = t.gameObject;
                    if (go == root && (root.GetComponent<LotoManager>() != null || root.GetComponent<LotoUIController>() != null || root.GetComponent<Camera>() != null))
                        continue;

                    bool isReferenced = referencedObjects.Contains(go);

                    bool isLegacyPanelName = go.name.ToLowerInvariant().Contains("panel") 
                        || go.name.ToLowerInvariant().Contains("canvas") 
                        || go.name.ToLowerInvariant().Contains("overlay")
                        || go.name.ToLowerInvariant().Contains("test_legacy")
                        || go.name.ToLowerInvariant().Contains("old_ui");

                    if (isReferenced && isLegacyPanelName)
                    {
                        if (go.activeSelf)
                        {
                            Undo.RecordObject(go, "Désactiver le panneau legacy référencé");
                            go.SetActive(false);
                            processedCount++;
                            Debug.Log($"[SmartLOTO Cleaner] Panneau legacy référencé désactivé avec sûreté : <b>{go.name}</b> (liaison sérialisée préservée).");
                        }
                    }
                    else if (!isReferenced && isLegacyPanelName)
                    {
                        if (go.activeSelf)
                        {
                            Undo.RecordObject(go, "Désactiver le panneau legacy orphelin");
                            go.SetActive(false);
                            processedCount++;
                            Debug.Log($"[SmartLOTO Cleaner] Objet legacy non-référencé désactivé : <b>{go.name}</b>.");
                        }
                    }
                }
            }

            Undo.CollapseUndoOperations(undoGroup);
            if (processedCount > 0)
            {
                EditorSceneManager.MarkSceneDirty(activeScene);
            }

            Debug.Log($"<color=#5EEAD4>[SmartLOTO Cleaner] Scan de la scène terminé : {processedCount} objets legacy désactivés en toute sécurité.</color>");
            return processedCount;
        }

        [MenuItem("SmartLOTO/Auditer les Assets Inutilisés", false, 102)]
        public static int AuditUnusedAssets()
        {
            string[] assetGuids = AssetDatabase.FindAssets("t:Texture2D t:Material t:GameObject", new[] { "Assets" });
            var allAssets = new HashSet<string>();

            foreach (var guid in assetGuids)
            {
                string path = AssetDatabase.GUIDToAssetPath(guid);
                if (!string.IsNullOrEmpty(path) && !path.Contains("StreamingAssets") && !path.Contains("/Editor/"))
                {
                    allAssets.Add(path);
                }
            }

            var activeScene = SceneManager.GetActiveScene();
            var usedAssets = new HashSet<string>();

            if (!string.IsNullOrEmpty(activeScene.path))
            {
                string[] dependencies = AssetDatabase.GetDependencies(activeScene.path, true);
                foreach (var dep in dependencies)
                {
                    usedAssets.Add(dep);
                }
            }

            var roots = activeScene.GetRootGameObjects();
            var rootDeps = EditorUtility.CollectDependencies(roots);
            foreach (var obj in rootDeps)
            {
                string path = AssetDatabase.GetAssetPath(obj);
                if (!string.IsNullOrEmpty(path))
                {
                    usedAssets.Add(path);
                }
            }

            var unused = allAssets.Where(a => !usedAssets.Contains(a)).ToList();

            Debug.Log($"<b>[SmartLOTO Audit Assets]</b> Total analysé : {allAssets.Count} | Dépendances actives : {usedAssets.Count} | Candidats non référencés : {unused.Count}");

            if (unused.Count > 0)
            {
                Debug.LogWarning($"<color=#FBBF24><b>[SmartLOTO Audit Assets] {unused.Count} assets hors StreamingAssets non référencés :</b></color>");
                foreach (var path in unused)
                {
                    Debug.Log($"   • Fichier candidat : {path}");
                }
            }
            else
            {
                Debug.Log("<color=#34D399><b>[SmartLOTO Audit Assets]</b> Dossier sain ! Aucun asset orphelin détecté hors dépendances actives.</color>");
            }

            return unused.Count;
        }
    }
}
#endif
