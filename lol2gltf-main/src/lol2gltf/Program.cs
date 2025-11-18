/*
 * lol2gltf - Modified Version
 * 
 * This is a modified version of lol2gltf, originally created by Crauzer.
 * Original repository: https://github.com/Crauzer/lol2gltf
 * 
 * MODIFICATIONS:
 * - Added ConvertGltfToStaticMesh method (gltf2static command)
 * - Added ConvertGltfToAnimation method (gltf2anm command)
 * 
 * Original work Copyright (C) [Year] Crauzer
 * Modifications Copyright (C) 2025 ritoshark
 * 
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 * 
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 * 
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <https://www.gnu.org/licenses/>.
 */

using BCnEncoder.Shared;
using CommandLine;
using CommunityToolkit.HighPerformance;
using LeagueToolkit.Core.Animation;
using LeagueToolkit.Core.Environment;
using LeagueToolkit.Core.Mesh;
using LeagueToolkit.Core.Meta;
using LeagueToolkit.IO.MapGeometryFile;
using LeagueToolkit.IO.SimpleSkinFile;
using LeagueToolkit.Meta;
using LeagueToolkit.Toolkit;
using SharpGLTF.Schema2;
using SixLabors.ImageSharp;
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Numerics;
using System.Reflection;
using System.Runtime.InteropServices;
using ImageSharpImage = SixLabors.ImageSharp.Image;
using LeagueTexture = LeagueToolkit.Core.Renderer.Texture;
using System.Diagnostics.CodeAnalysis;
using LeagueToolkit.Toolkit.Gltf;

namespace lol2gltf;

class Program
{
    static void Main(string[] args)
    {
        CommandLine.Parser.Default
            .ParseArguments<SkinnedMeshToGltfOptions, MapGeometryToGltfOptions, GltfToSkinnedMeshOptions, GltfToStaticMeshOptions, GltfToAnimationOptions>(args)
            .MapResult(
                (SkinnedMeshToGltfOptions opts) => ConvertSkinnedMeshToGltf(opts),
                (MapGeometryToGltfOptions opts) => ConvertMapGeometryToGltf(opts),
                (GltfToSkinnedMeshOptions opts) => ConvertGltfToSkinnedMesh(opts),
                (GltfToStaticMeshOptions opts) => ConvertGltfToStaticMesh(opts),
                (GltfToAnimationOptions opts) => ConvertGltfToAnimation(opts),
                HandleErrors
            );
    }

    private static int HandleErrors(IEnumerable<Error> errors)
    {
        return -1;
    }

    private static int ConvertSkinnedMeshToGltf(SkinnedMeshToGltfOptions options)
    {
        if (options.MaterialNames.Count() != options.TexturePaths.Count())
            throw new InvalidOperationException("Material name count and Animation path count must be equal");

        // Convert textures to png
        IEnumerable<(string, Stream)> textures = options.MaterialNames
            .Zip(options.TexturePaths)
            .Select(x =>
            {
                using FileStream textureFileStream = File.OpenRead(x.Second);
                LeagueTexture texture = LeagueTexture.Load(textureFileStream);

                ReadOnlyMemory2D<ColorRgba32> mipMap = texture.Mips[0];
                using ImageSharpImage image = mipMap.ToImage();

                MemoryStream imageStream = new();
                image.SaveAsPng(imageStream);
                imageStream.Seek(0, SeekOrigin.Begin);

                return (x.First, (Stream)imageStream);
            });

        IEnumerable<(string, IAnimationAsset)> animations = !string.IsNullOrEmpty(options.AnimationsPath)
            ? LoadAnimations(options.AnimationsPath)
            : Enumerable.Empty<(string, IAnimationAsset)>();

        using FileStream skeletonStream = File.OpenRead(options.SkeletonPath);

        SkinnedMesh simpleSkin = SkinnedMesh.ReadFromSimpleSkin(options.SimpleSkinPath);
        RigResource skeleton = new(skeletonStream);

        ModelRoot gltf = simpleSkin.ToGltf(skeleton, textures, animations);
        
        gltf.Save(options.GltfPath);

        return 1;
    }

    private static int ConvertGltfToSkinnedMesh(GltfToSkinnedMeshOptions options)
    {
        string skeletonPath = string.IsNullOrEmpty(options.SkeletonPath) switch
        {
            true => Path.ChangeExtension(options.SimpleSkinPath, "skl"),
            false => options.SkeletonPath
        };

        ModelRoot gltf = ModelRoot.Load(options.GltfPath);

        var (simpleSkin, rig) = gltf.ToRiggedMesh();

        using FileStream simpleSkinStream = File.Create(options.SimpleSkinPath);
        simpleSkin.WriteSimpleSkin(simpleSkinStream);

        using FileStream rigStream = File.Create(skeletonPath);
        rig.Write(rigStream);

        return 1;
    }

    [RequiresUnreferencedCode("Calls System.Reflection.Assembly.GetExportedTypes()")]
    private static int ConvertMapGeometryToGltf(MapGeometryToGltfOptions options)
    {
        MapGeometryGltfConversionContext conversionContext =
            new(
                MetaEnvironment.Create(
                    Assembly.Load("LeagueToolkit.Meta.Classes").GetExportedTypes().Where(x => x.IsClass)
                ),
                new()
                {
                    FlipAcrossX = options.FlipAcrossX,
                    GameDataPath = options.GameDataPath,
                    LayerGroupingPolicy = options.LayerGroupingPolicy,
                    TextureQuality = options.TextureQuality
                }
            );

        using FileStream environmentAssetStream = File.OpenRead(options.MapGeometryPath);
        using FileStream materialsBinStream = File.OpenRead(options.MaterialsBinPath);

        using EnvironmentAsset mapGeometry = new(environmentAssetStream);
        BinTree materialsBin = new(materialsBinStream);

        mapGeometry.ToGltf(materialsBin, conversionContext).Save(options.GltfPath);

        return 1;
    }

    private static int ConvertGltfToStaticMesh(GltfToStaticMeshOptions options)
    {
        ModelRoot gltf = ModelRoot.Load(options.GltfPath);

        // Convert GLTF to StaticMesh
        StaticMesh staticMesh = gltf.ToStaticMesh();

        // Determine if we should save as SCB or SCO based on file extension
        string extension = Path.GetExtension(options.OutputPath).ToLowerInvariant();
        using FileStream outputStream = File.Create(options.OutputPath);

        if (extension == ".scb")
        {
            staticMesh.WriteBinary(outputStream);
        }
        else if (extension == ".sco")
        {
            staticMesh.WriteAscii(outputStream);
        }
        else
        {
            throw new InvalidOperationException("Output file must have .scb or .sco extension");
        }

        return 1;
    }

    private static int ConvertGltfToAnimation(GltfToAnimationOptions options)
    {
        ModelRoot gltf = ModelRoot.Load(options.GltfPath);

        // Create output directory if it doesn't exist
        Directory.CreateDirectory(options.OutputPath);

        // Load skeleton if provided for validation
        RigResource skeleton = null;
        if (!string.IsNullOrEmpty(options.SkeletonPath) && File.Exists(options.SkeletonPath))
        {
            using FileStream skeletonStream = File.OpenRead(options.SkeletonPath);
            skeleton = new RigResource(skeletonStream);
        }

        // Extract animations from glTF
        // Try to use LeagueToolkit's ToAnimations extension method via reflection
        IEnumerable<(string, IAnimationAsset)> animations;
        
        try
        {
            // Try to find the extension method class using reflection
            // Get the assembly from a known LeagueToolkit type
            var knownType = typeof(SkinnedMesh); // This is from LeagueToolkit.IO.SimpleSkinFile
            var toolkitAssembly = knownType.Assembly;
            
            // Also check other loaded assemblies
            if (toolkitAssembly == null)
            {
                toolkitAssembly = AppDomain.CurrentDomain.GetAssemblies()
                    .FirstOrDefault(a => a.GetName().Name?.Contains("LeagueToolkit") == true);
            }
            
            Type[] types = null;
            try
            {
                types = toolkitAssembly?.GetTypes();
            }
            catch (ReflectionTypeLoadException ex)
            {
                // Some types couldn't be loaded, use the ones that were loaded
                types = ex.Types.Where(t => t != null).ToArray();
            }
            
            var extensionType = types?
                .FirstOrDefault(t => t.Name == "GltfExtensions" && 
                                     t.Namespace == "LeagueToolkit.Toolkit.Gltf");
            
            if (extensionType != null)
            {
                var toAnimationsMethod = extensionType.GetMethods()
                    .FirstOrDefault(m => m.Name == "ToAnimations" && 
                                         m.IsStatic && 
                                         m.GetParameters().Length >= 1 &&
                                         m.GetParameters()[0].ParameterType == typeof(ModelRoot));
                
                if (toAnimationsMethod != null)
                {
                    // Extension method exists, call it
                    var parameters = skeleton != null 
                        ? new object[] { gltf, skeleton } 
                        : new object[] { gltf };
                    var result = toAnimationsMethod.Invoke(null, parameters);
                    animations = (IEnumerable<(string, IAnimationAsset)>)result;
                }
                else
                {
                    throw new MissingMethodException("ToAnimations method not found");
                }
            }
            else
            {
                throw new TypeLoadException("GltfExtensions type not found");
            }
        }
        catch (Exception ex)
        {
            // Extension method doesn't exist or failed, extract manually
            Console.WriteLine($"Note: ToAnimations extension method not available, using manual extraction: {ex.Message}");
            try
            {
                animations = ExtractAnimationsFromGltf(gltf, skeleton);
            }
            catch (Exception ex2)
            {
                Console.WriteLine($"Warning: Failed to extract animations: {ex2.Message}");
                animations = Enumerable.Empty<(string, IAnimationAsset)>();
            }
        }

        if (!animations.Any())
        {
            Console.WriteLine("No animations found in glTF file");
            return 0;
        }

        // Save each animation as ANM file
        int count = 0;
        foreach (var (name, animation) in animations)
        {
            Console.WriteLine($"[ANM Export] ========================================");
            Console.WriteLine($"[ANM Export] Exporting animation: {name}");
            Console.WriteLine($"[ANM Export] ========================================");
            
            string anmPath = Path.Combine(options.OutputPath, $"{name}.anm");
            
            // Try to use reflection to call Write method on the animation object
            var writeMethod = animation.GetType().GetMethod("Write", new[] { typeof(Stream) });
            if (writeMethod != null)
            {
                Console.WriteLine($"[ANM Export] Using Write method on {animation.GetType().Name}");
                using FileStream anmStream = File.Create(anmPath);
                writeMethod.Invoke(animation, new object[] { anmStream });
            }
            else
            {
                // AnimationAsset doesn't have a Write method, so we need to write it directly
                // This happens when using manual extraction - the animation was created by writing to MemoryStream
                // and loading it back, so we need to extract the data and write it again
                // For now, we'll write it directly from the glTF data
                Console.WriteLine($"[ANM Export] Writing directly from glTF data (no Write method available)");
                WriteAnimationDirectlyFromGltf(gltf, name, anmPath, skeleton);
            }
            
            Console.WriteLine($"[ANM Export] ✓ Exported: {name}.anm");
            count++;
        }

        Console.WriteLine($"[ANM Export] ========================================");
        Console.WriteLine($"[ANM Export] Successfully exported {count} animation(s)");
        Console.WriteLine($"[ANM Export] ========================================");
        return 1;
    }

    private static IEnumerable<(string, IAnimationAsset)> ExtractAnimationsFromGltf(ModelRoot gltf, RigResource skeleton)
    {
        // Check if glTF has animations
        if (gltf.LogicalAnimations == null || gltf.LogicalAnimations.Count == 0)
        {
            return Enumerable.Empty<(string, IAnimationAsset)>();
        }

        // If skeleton is provided, use it for bone mapping
        // Otherwise, we'll need to extract bone information from the glTF
        var animations = new List<(string, IAnimationAsset)>();

        foreach (var gltfAnimation in gltf.LogicalAnimations)
        {
            string animationName = gltfAnimation.Name ?? "Animation";
            
            // Create AnimationAsset from glTF animation
            // This is a simplified version - you may need to adjust based on LeagueToolkit's AnimationAsset structure
            try
            {
                var animationAsset = ConvertGltfAnimationToAnimationAsset(gltfAnimation, gltf, skeleton);
                animations.Add((animationName, animationAsset));
            }
            catch (OverflowException ex)
            {
                Console.WriteLine($"Warning: Failed to convert animation '{animationName}': Arithmetic overflow - {ex.Message}");
                Console.WriteLine($"  Stack trace: {ex.StackTrace}");
            }
            catch (ReflectionTypeLoadException ex)
            {
                string loaderErrors = string.Join("; ", ex.LoaderExceptions?.Where(e => e != null).Select(e => e.Message) ?? new string[0]);
                Console.WriteLine($"Warning: Failed to convert animation '{animationName}': Unable to load one or more of the requested types. Loader errors: {loaderErrors}");
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Warning: Failed to convert animation '{animationName}': {ex.Message}");
                if (ex.InnerException != null)
                {
                    Console.WriteLine($"  Inner exception: {ex.InnerException.Message}");
                }
            }
        }

        return animations;
    }

    private static void WriteAnimationDirectlyFromGltf(ModelRoot gltf, string animationName, string outputPath, RigResource skeleton)
    {
        // Find the animation in glTF
        var gltfAnimation = gltf.LogicalAnimations?.FirstOrDefault(a => (a.Name ?? "Animation") == animationName);
        if (gltfAnimation == null)
        {
            throw new InvalidOperationException($"Animation '{animationName}' not found in glTF file");
        }

        // Extract the animation data and write directly
        var (jointNames, frameCount, frameDuration, fps, nodeKeyframes, nodeRotations, nodeScales, translationCurveSamplers, rotationCurveSamplers, scaleCurveSamplers) = 
            ExtractAnimationDataFromGltf(gltfAnimation, gltf, skeleton);

        using FileStream outputStream = File.Create(outputPath);
        WriteUncompressedAnimationAssetV5(
            outputStream,
            jointNames,
            frameCount,
            frameDuration,
            fps,
            nodeKeyframes,
            nodeRotations,
            nodeScales,
            translationCurveSamplers,
            rotationCurveSamplers,
            scaleCurveSamplers,
            gltf
        );
    }

    private static (List<string> jointNames, int frameCount, float frameDuration, float fps,
        Dictionary<string, Dictionary<string, List<(float time, System.Numerics.Vector3 value)>>> nodeKeyframes,
        Dictionary<string, Dictionary<string, List<(float time, System.Numerics.Quaternion value)>>> nodeRotations,
        Dictionary<string, Dictionary<string, List<(float time, System.Numerics.Vector3 value)>>> nodeScales,
        Dictionary<string, object> translationCurveSamplers,
        Dictionary<string, object> rotationCurveSamplers,
        Dictionary<string, object> scaleCurveSamplers)
        ExtractAnimationDataFromGltf(SharpGLTF.Schema2.Animation gltfAnimation, ModelRoot gltf, RigResource skeleton)
    {
        Console.WriteLine($"[ANM Export] Starting animation extraction for: {gltfAnimation.Name ?? "Unnamed"}");
        
        // Get the skin/joints from glTF
        var skin = gltf.LogicalSkins?.FirstOrDefault();
        if (skin == null)
        {
            throw new InvalidOperationException("No skin found in glTF file");
        }

        // Get joint names - prefer skeleton if provided, otherwise use glTF skin
        List<string> jointNames = new();
        
        if (skeleton != null)
        {
            Console.WriteLine($"[ANM Export] Using skeleton with {skeleton.Joints.Count} joints");
            // Use skeleton joint names
            for (int i = 0; i < skeleton.Joints.Count; i++)
            {
                var joint = skeleton.Joints[i];
                jointNames.Add(joint.Name);
            }
        }
        else
        {
            Console.WriteLine($"[ANM Export] Using glTF skin with {skin.JointsCount} joints");
            // Extract from glTF skin
            foreach (var jointNode in skin.Joints)
            {
                string jointName = jointNode.Name ?? $"Joint_{jointNode.LogicalIndex}";
                if (!jointNames.Contains(jointName))
                {
                    jointNames.Add(jointName);
                }
            }
        }
        Console.WriteLine($"[ANM Export] Total joints: {jointNames.Count}");

        // Extract keyframe data from glTF animation channels
        // Store raw keyframes keyed by node name (for compatibility with existing code)
        Dictionary<string, Dictionary<string, List<(float time, System.Numerics.Vector3 value)>>> nodeKeyframes = new();
        Dictionary<string, Dictionary<string, List<(float time, System.Numerics.Quaternion value)>>> nodeRotations = new();
        Dictionary<string, Dictionary<string, List<(float time, System.Numerics.Vector3 value)>>> nodeScales = new();
        
        // Store curve samplers for proper evaluation (fixes micro stutters)
        Dictionary<string, object> translationCurveSamplers = new(); // ICurveSampler<Vector3>
        Dictionary<string, object> rotationCurveSamplers = new(); // ICurveSampler<Quaternion>
        Dictionary<string, object> scaleCurveSamplers = new(); // ICurveSampler<Vector3>
        
        float maxTime = 0f;
        int channelCount = 0;

        Console.WriteLine($"[ANM Export] Processing {gltfAnimation.Channels.Count} animation channels...");

        // Iterate through channels to extract keyframe data
        for (int channelIndex = 0; channelIndex < gltfAnimation.Channels.Count; channelIndex++)
        {
            var channel = gltfAnimation.Channels[channelIndex];
            var targetNode = channel.TargetNode;
            if (targetNode == null)
            {
                Console.WriteLine($"[ANM Export] WARNING: Channel {channelIndex} has no target node, skipping");
                continue;
            }

            string nodeName = targetNode.Name ?? $"Node_{targetNode.LogicalIndex}";

            // Get the target path property (PropertyPath enum: translation, rotation, scale)
            var targetPathProp = channel.GetType().GetProperty("TargetNodePath");
            if (targetPathProp == null)
            {
                Console.WriteLine($"[ANM Export] WARNING: Channel {channelIndex} (node: {nodeName}) missing TargetNodePath property, skipping");
                continue;
            }

            var targetPath = targetPathProp.GetValue(channel);
            if (targetPath == null)
            {
                Console.WriteLine($"[ANM Export] WARNING: Channel {channelIndex} (node: {nodeName}) has null TargetNodePath, skipping");
                continue;
            }

            // Use the public methods to get samplers based on target path
            // These methods call _GetSampler() internally: LogicalParent._Samplers[_sampler]
            object sampler = null;
            string pathType = "";
            
            // Check the PropertyPath enum value
            if (targetPath.Equals(SharpGLTF.Schema2.PropertyPath.translation))
            {
                var getTranslationSamplerMethod = channel.GetType().GetMethod("GetTranslationSampler");
                if (getTranslationSamplerMethod != null)
                {
                    sampler = getTranslationSamplerMethod.Invoke(channel, null);
                    pathType = "translation";
                }
            }
            else if (targetPath.Equals(SharpGLTF.Schema2.PropertyPath.rotation))
            {
                var getRotationSamplerMethod = channel.GetType().GetMethod("GetRotationSampler");
                if (getRotationSamplerMethod != null)
                {
                    sampler = getRotationSamplerMethod.Invoke(channel, null);
                    pathType = "rotation";
                }
            }
            else if (targetPath.Equals(SharpGLTF.Schema2.PropertyPath.scale))
            {
                var getScaleSamplerMethod = channel.GetType().GetMethod("GetScaleSampler");
                if (getScaleSamplerMethod != null)
                {
                    sampler = getScaleSamplerMethod.Invoke(channel, null);
                    pathType = "scale";
                }
            }

            // Fallback: use _GetSampler via reflection
            if (sampler == null)
            {
                var getSamplerMethod = channel.GetType().GetMethod("_GetSampler", 
                    System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
            if (getSamplerMethod != null)
                {
                    try
                    {
                        sampler = getSamplerMethod.Invoke(channel, null);
                        // Determine path type from targetPath
                        if (targetPath.Equals(SharpGLTF.Schema2.PropertyPath.translation))
                            pathType = "translation";
                        else if (targetPath.Equals(SharpGLTF.Schema2.PropertyPath.rotation))
                            pathType = "rotation";
                        else if (targetPath.Equals(SharpGLTF.Schema2.PropertyPath.scale))
                            pathType = "scale";
                    }
                    catch (Exception ex)
                    {
                        Console.WriteLine($"[ANM Export] DEBUG: Failed to call _GetSampler: {ex.Message}");
                    }
                }
            }

            if (sampler == null || string.IsNullOrEmpty(pathType))
            {
                Console.WriteLine($"[ANM Export] WARNING: Channel {channelIndex} (node: {nodeName}) sampler not found or unsupported path: {targetPath}, skipping");
                continue;
            }

            // Get input and output accessors
            var inputProp = sampler.GetType().GetProperty("Input");
            var outputProp = sampler.GetType().GetProperty("Output") ?? sampler.GetType().GetProperty("OutputAccessor");
            
            if (inputProp == null || outputProp == null)
            {
                Console.WriteLine($"[ANM Export] WARNING: Channel {channelIndex} (node: {nodeName}) missing accessors, skipping");
                continue;
            }

            var inputAccessor = inputProp.GetValue(sampler);
            var outputAccessor = outputProp.GetValue(sampler);

            var inputLogicalIndex = inputAccessor.GetType().GetProperty("LogicalIndex")?.GetValue(inputAccessor);
            var outputLogicalIndex = outputAccessor.GetType().GetProperty("LogicalIndex")?.GetValue(outputAccessor);

            if (inputLogicalIndex == null || outputLogicalIndex == null)
            {
                Console.WriteLine($"[ANM Export] WARNING: Channel {channelIndex} (node: {nodeName}) missing logical indices, skipping");
                continue;
            }

            var inputAcc = gltf.LogicalAccessors[(int)inputLogicalIndex];
            var outputAcc = gltf.LogicalAccessors[(int)outputLogicalIndex];

            // Get time values (keyframe times)
            var times = inputAcc.AsScalarArray().Select(t => (float)t).ToArray();
            if (times.Length > 0)
            {
                maxTime = Math.Max(maxTime, times.Max());
            }

            // Store BOTH keyframes AND curve samplers for evaluation
            // Keyframes are needed as fallback, curve samplers for proper interpolation
            if (pathType == "translation")
            {
                if (!nodeKeyframes.ContainsKey(nodeName))
                    nodeKeyframes[nodeName] = new Dictionary<string, List<(float, System.Numerics.Vector3)>>();
                
                // Extract and store keyframe data
                var translations = outputAcc.AsVector3Array().Select(v => new System.Numerics.Vector3((float)v.X, (float)v.Y, (float)v.Z)).ToArray();
                nodeKeyframes[nodeName]["translation"] = times.Zip(translations, (t, v) => (t, v)).ToList();
                
                // Also store curve sampler for proper evaluation
                // CreateCurveSampler is defined on IAnimationSampler<T>, so we need to call it through the interface
                var samplerInterface = typeof(SharpGLTF.Schema2.IAnimationSampler<>).MakeGenericType(typeof(System.Numerics.Vector3));
                if (samplerInterface.IsAssignableFrom(sampler.GetType()))
                {
                    try
                    {
                        // Get the CreateCurveSampler method from the interface
                        var createCurveSamplerMethod = samplerInterface.GetMethod("CreateCurveSampler", new[] { typeof(bool) });
                        if (createCurveSamplerMethod != null)
                        {
                            // Call through interface - the sampler already implements it
                            var curveSampler = createCurveSamplerMethod.Invoke(sampler, new object[] { true });
                            if (curveSampler != null && !translationCurveSamplers.ContainsKey(nodeName))
                                translationCurveSamplers[nodeName] = curveSampler;
                        }
                    }
                    catch (Exception ex)
                    {
                        Console.WriteLine($"[ANM Export] WARNING: Failed to create translation curve sampler for '{nodeName}': {ex.Message}");
                    }
                }
                
                channelCount++;
                Console.WriteLine($"[ANM Export]   - Node '{nodeName}': {translations.Length} translation keyframes (time range: {times.Min():F3} - {times.Max():F3}s)");
            }
            else if (pathType == "rotation")
            {
                if (!nodeRotations.ContainsKey(nodeName))
                    nodeRotations[nodeName] = new Dictionary<string, List<(float, System.Numerics.Quaternion)>>();
                
                // Extract and store keyframe data
                var rotations = outputAcc.AsQuaternionArray().Select(q => new System.Numerics.Quaternion((float)q.X, (float)q.Y, (float)q.Z, (float)q.W)).ToArray();
                nodeRotations[nodeName]["rotation"] = times.Zip(rotations, (t, v) => (t, v)).ToList();
                
                // Also store curve sampler for proper evaluation
                // CreateCurveSampler is defined on IAnimationSampler<T>, so we need to call it through the interface
                var samplerInterface = typeof(SharpGLTF.Schema2.IAnimationSampler<>).MakeGenericType(typeof(System.Numerics.Quaternion));
                if (samplerInterface.IsAssignableFrom(sampler.GetType()))
                {
                    try
                    {
                        // Get the CreateCurveSampler method from the interface
                        var createCurveSamplerMethod = samplerInterface.GetMethod("CreateCurveSampler", new[] { typeof(bool) });
                        if (createCurveSamplerMethod != null)
                        {
                            // Call through interface - the sampler already implements it
                            var curveSampler = createCurveSamplerMethod.Invoke(sampler, new object[] { true });
                            if (curveSampler != null && !rotationCurveSamplers.ContainsKey(nodeName))
                                rotationCurveSamplers[nodeName] = curveSampler;
                        }
                    }
                    catch (Exception ex)
                    {
                        Console.WriteLine($"[ANM Export] WARNING: Failed to create rotation curve sampler for '{nodeName}': {ex.Message}");
                    }
                }
                
                channelCount++;
                Console.WriteLine($"[ANM Export]   - Node '{nodeName}': {rotations.Length} rotation keyframes (time range: {times.Min():F3} - {times.Max():F3}s)");
            }
            else if (pathType == "scale")
            {
                if (!nodeScales.ContainsKey(nodeName))
                    nodeScales[nodeName] = new Dictionary<string, List<(float, System.Numerics.Vector3)>>();
                
                // Extract and store keyframe data
                var scales = outputAcc.AsVector3Array().Select(v => new System.Numerics.Vector3((float)v.X, (float)v.Y, (float)v.Z)).ToArray();
                nodeScales[nodeName]["scale"] = times.Zip(scales, (t, v) => (t, v)).ToList();
                
                // Also store curve sampler for proper evaluation
                // CreateCurveSampler is defined on IAnimationSampler<T>, so we need to call it through the interface
                var samplerInterface = typeof(SharpGLTF.Schema2.IAnimationSampler<>).MakeGenericType(typeof(System.Numerics.Vector3));
                if (samplerInterface.IsAssignableFrom(sampler.GetType()))
                {
                    try
                    {
                        // Get the CreateCurveSampler method from the interface
                        var createCurveSamplerMethod = samplerInterface.GetMethod("CreateCurveSampler", new[] { typeof(bool) });
                        if (createCurveSamplerMethod != null)
                        {
                            // Call through interface - the sampler already implements it
                            var curveSampler = createCurveSamplerMethod.Invoke(sampler, new object[] { true });
                            if (curveSampler != null && !scaleCurveSamplers.ContainsKey(nodeName))
                                scaleCurveSamplers[nodeName] = curveSampler;
                        }
                    }
                    catch (Exception ex)
                    {
                        Console.WriteLine($"[ANM Export] WARNING: Failed to create scale curve sampler for '{nodeName}': {ex.Message}");
                    }
                }
                
                channelCount++;
                Console.WriteLine($"[ANM Export]   - Node '{nodeName}': {scales.Length} scale keyframes (time range: {times.Min():F3} - {times.Max():F3}s)");
            }
        }

        Console.WriteLine($"[ANM Export] Processed {channelCount} channels, max time: {maxTime:F3}s");

        // Create curve samplers from keyframes for joints that don't have them yet
        // This ensures ALL joints use smooth interpolation, eliminating stuttering
        foreach (var kvp in nodeKeyframes)
        {
            string nodeName = kvp.Key;
            foreach (var pathKvp in kvp.Value)
            {
                string path = pathKvp.Key;
                var keyframes = pathKvp.Value;
                
                if (path == "translation" && !translationCurveSamplers.ContainsKey(nodeName) && keyframes.Count > 0)
                {
                    try
                    {
                        // Use CreateSampler extension method via reflection
                        // CreateSampler(this IEnumerable<(Single, Vector3)> collection, bool isLinear, bool optimize)
                        var createSamplerMethods = typeof(SharpGLTF.Animations.CurveSampler).GetMethods(System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.Static)
                            .Where(m => m.Name == "CreateSampler" && m.GetParameters().Length == 3)
                            .ToList();
                        
                        // Find the one that takes IEnumerable<(float, Vector3)>
                        foreach (var method in createSamplerMethods)
                        {
                            var firstParam = method.GetParameters()[0];
                            if (firstParam.ParameterType.IsGenericType)
                            {
                                var genArgs = firstParam.ParameterType.GetGenericArguments();
                                if (genArgs.Length == 1 && genArgs[0].IsGenericType)
                                {
                                    var tupleArgs = genArgs[0].GetGenericArguments();
                                    if (tupleArgs.Length == 2 && tupleArgs[0] == typeof(float) && tupleArgs[1] == typeof(System.Numerics.Vector3))
                                    {
                                        var curveSampler = method.Invoke(null, new object[] { keyframes, true, true });
                                        if (curveSampler != null)
                                        {
                                            translationCurveSamplers[nodeName] = curveSampler;
                                            break;
                                        }
                                    }
                                }
                            }
                        }
                    }
                    catch
                    {
                        // Silently fail - will use manual interpolation
                    }
                }
                else if (path == "scale" && !scaleCurveSamplers.ContainsKey(nodeName) && keyframes.Count > 0)
                {
                    try
                    {
                        var createSamplerMethods = typeof(SharpGLTF.Animations.CurveSampler).GetMethods(System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.Static)
                            .Where(m => m.Name == "CreateSampler" && m.GetParameters().Length == 3)
                            .ToList();
                        
                        foreach (var method in createSamplerMethods)
                        {
                            var firstParam = method.GetParameters()[0];
                            if (firstParam.ParameterType.IsGenericType)
                            {
                                var genArgs = firstParam.ParameterType.GetGenericArguments();
                                if (genArgs.Length == 1 && genArgs[0].IsGenericType)
                                {
                                    var tupleArgs = genArgs[0].GetGenericArguments();
                                    if (tupleArgs.Length == 2 && tupleArgs[0] == typeof(float) && tupleArgs[1] == typeof(System.Numerics.Vector3))
                                    {
                                        var curveSampler = method.Invoke(null, new object[] { keyframes, true, true });
                                        if (curveSampler != null)
                                        {
                                            scaleCurveSamplers[nodeName] = curveSampler;
                                            break;
                                        }
                                    }
                                }
                            }
                        }
                    }
                    catch { }
                }
            }
        }
        
        foreach (var kvp in nodeRotations)
        {
            string nodeName = kvp.Key;
            foreach (var pathKvp in kvp.Value)
            {
                string path = pathKvp.Key;
                var keyframes = pathKvp.Value;
                
                if (path == "rotation" && !rotationCurveSamplers.ContainsKey(nodeName) && keyframes.Count > 0)
                {
                    try
                    {
                        var createSamplerMethods = typeof(SharpGLTF.Animations.CurveSampler).GetMethods(System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.Static)
                            .Where(m => m.Name == "CreateSampler" && m.GetParameters().Length == 3)
                            .ToList();
                        
                        foreach (var method in createSamplerMethods)
                        {
                            var firstParam = method.GetParameters()[0];
                            if (firstParam.ParameterType.IsGenericType)
                            {
                                var genArgs = firstParam.ParameterType.GetGenericArguments();
                                if (genArgs.Length == 1 && genArgs[0].IsGenericType)
                                {
                                    var tupleArgs = genArgs[0].GetGenericArguments();
                                    if (tupleArgs.Length == 2 && tupleArgs[0] == typeof(float) && tupleArgs[1] == typeof(System.Numerics.Quaternion))
                                    {
                                        var curveSampler = method.Invoke(null, new object[] { keyframes, true, true });
                                        if (curveSampler != null)
                                        {
                                            rotationCurveSamplers[nodeName] = curveSampler;
                                            break;
                                        }
                                    }
                                }
                            }
                        }
                    }
                    catch { }
                }
            }
        }
        
        foreach (var kvp in nodeScales)
        {
            string nodeName = kvp.Key;
            foreach (var pathKvp in kvp.Value)
            {
                string path = pathKvp.Key;
                var keyframes = pathKvp.Value;
                
                if (path == "scale" && !scaleCurveSamplers.ContainsKey(nodeName) && keyframes.Count > 0)
                {
                    try
                    {
                        var createSamplerMethods = typeof(SharpGLTF.Animations.CurveSampler).GetMethods(System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.Static)
                            .Where(m => m.Name == "CreateSampler" && m.GetParameters().Length == 3)
                            .ToList();
                        
                        foreach (var method in createSamplerMethods)
                        {
                            var firstParam = method.GetParameters()[0];
                            if (firstParam.ParameterType.IsGenericType)
                            {
                                var genArgs = firstParam.ParameterType.GetGenericArguments();
                                if (genArgs.Length == 1 && genArgs[0].IsGenericType)
                                {
                                    var tupleArgs = genArgs[0].GetGenericArguments();
                                    if (tupleArgs.Length == 2 && tupleArgs[0] == typeof(float) && tupleArgs[1] == typeof(System.Numerics.Vector3))
                                    {
                                        var curveSampler = method.Invoke(null, new object[] { keyframes, true, true });
                                        if (curveSampler != null)
                                        {
                                            scaleCurveSamplers[nodeName] = curveSampler;
                                            break;
                                        }
                                    }
                                }
                            }
                        }
                    }
                    catch { }
                }
            }
        }

        // Calculate frame count and duration - REVERSING CreateGltfAnimation logic
        // CreateGltfAnimation uses: frameCount = (int)(animation.Fps * animation.Duration)
        // We need to determine FPS and calculate frameCount the same way
        const float fps = 30f; // Standard FPS for LoL animations (can be adjusted if needed)
        float duration = maxTime;
        
        // Calculate frameCount exactly like CreateGltfAnimation: (int)(fps * duration)
        int frameCount = (int)(fps * duration);
        if (frameCount < 1)
        {
            frameCount = 1; // At least 1 frame
        }
        
        float frameDuration = 1f / fps;

        Console.WriteLine($"[ANM Export] Animation parameters:");
        Console.WriteLine($"[ANM Export]   - Duration: {duration:F3}s");
        Console.WriteLine($"[ANM Export]   - FPS: {fps}");
        Console.WriteLine($"[ANM Export]   - Frame count: {frameCount}");
        Console.WriteLine($"[ANM Export]   - Frame duration: {frameDuration:F6}s");

        return (jointNames, frameCount, frameDuration, fps, nodeKeyframes, nodeRotations, nodeScales, translationCurveSamplers, rotationCurveSamplers, scaleCurveSamplers);
    }

    private static IAnimationAsset ConvertGltfAnimationToAnimationAsset(SharpGLTF.Schema2.Animation gltfAnimation, ModelRoot gltf, RigResource skeleton)
    {
        // Extract animation data using shared method
        var (jointNames, frameCount, frameDuration, fps, nodeKeyframes, nodeRotations, nodeScales, translationCurveSamplers, rotationCurveSamplers, scaleCurveSamplers) = 
            ExtractAnimationDataFromGltf(gltfAnimation, gltf, skeleton);

        // Since AnimationAsset only has a read constructor, we need to write the ANM file format directly
        // We'll create a temporary stream, write the file, then load it back
        try
        {
            using MemoryStream tempStream = new();
            WriteUncompressedAnimationAssetV5(
                tempStream,
                jointNames,
                frameCount,
                frameDuration,
                fps,
                nodeKeyframes,
                nodeRotations,
                nodeScales,
                translationCurveSamplers,
                rotationCurveSamplers,
                scaleCurveSamplers,
                gltf
            );
            
            tempStream.Position = 0;
            return AnimationAsset.Load(tempStream);
        }
        catch (OverflowException ex)
        {
            throw new InvalidOperationException($"Overflow during ANM file writing: {ex.Message}. FrameCount={frameCount}, JointCount={jointNames.Count}", ex);
        }
    }

    private static void WriteUncompressedAnimationAssetV5(
        Stream stream,
        List<string> jointNames,
        int frameCount,
        float frameDuration,
        float fps,
        Dictionary<string, Dictionary<string, List<(float time, System.Numerics.Vector3 value)>>> nodeKeyframes,
        Dictionary<string, Dictionary<string, List<(float time, System.Numerics.Quaternion value)>>> nodeRotations,
        Dictionary<string, Dictionary<string, List<(float time, System.Numerics.Vector3 value)>>> nodeScales,
        Dictionary<string, object> translationCurveSamplers,
        Dictionary<string, object> rotationCurveSamplers,
        Dictionary<string, object> scaleCurveSamplers,
        ModelRoot gltf)
    {
        using BinaryWriter bw = new(stream, System.Text.Encoding.UTF8, true);
        
        // Write magic and version
        bw.Write(System.Text.Encoding.ASCII.GetBytes("r3d2anmd"));
        bw.Write(5u); // Version
        
        long resourceSizePos = bw.BaseStream.Position;
        bw.Write(0u); // Resource size - will write at end
        
        bw.Write(0u); // Format token (not validated in read)
        bw.Write(5u); // Version again
        bw.Write(0u); // Flags
        
        int trackCount = jointNames.Count;
        bw.Write(trackCount);
        bw.Write(frameCount);
        bw.Write(frameDuration);
        
        // Reserve space for offsets (6 int32s)
        long offsetsPos = bw.BaseStream.Position;
        bw.Write(0); // jointNameHashesOffset
        bw.Write(0); // assetNameOffset
        bw.Write(0); // timeOffset
        bw.Write(0); // vectorPaletteOffset
        bw.Write(0); // quatPaletteOffset
        bw.Write(0); // framesOffset
        
        // Build palettes and frame data
        // First, collect all frame data for all joints
        List<System.Numerics.Vector3> vectorPalette = new();
        List<System.Numerics.Quaternion> quatPalette = new();
        
        // Store frame data per joint hash, in the order of jointNames
        List<uint> jointHashes = new();
        List<List<(ushort translationId, ushort scaleId, ushort rotationId)>> allJointFrames = new();
        
        Console.WriteLine($"[ANM Export] Building animation data for {jointNames.Count} joints, {frameCount} frames...");
        Console.WriteLine($"[ANM Export] DEBUG: Created {translationCurveSamplers.Count} translation curve samplers, {rotationCurveSamplers.Count} rotation curve samplers, {scaleCurveSamplers.Count} scale curve samplers");
        
        // Debug: Log available node names
        if (nodeKeyframes.Count > 0 || nodeRotations.Count > 0 || nodeScales.Count > 0)
        {
            var allNodeNames = new HashSet<string>();
            allNodeNames.UnionWith(nodeKeyframes.Keys);
            allNodeNames.UnionWith(nodeRotations.Keys);
            allNodeNames.UnionWith(nodeScales.Keys);
            Console.WriteLine($"[ANM Export] DEBUG: Found animation data for {allNodeNames.Count} nodes: {string.Join(", ", allNodeNames.Take(10))}...");
            if (jointNames.Count > 0)
                Console.WriteLine($"[ANM Export] DEBUG: First few joint names: {string.Join(", ", jointNames.Take(10))}");
        }
        
        // Process each joint in order
        int jointsWithAnimation = 0;
        int jointsUsingCurveSamplers = 0;
        List<string> jointsNotUsingCurveSamplers = new();
        for (int jointIdx = 0; jointIdx < jointNames.Count; jointIdx++)
        {
            string jointName = jointNames[jointIdx];
            uint jointHash = GetJointHash(jointName);
            jointHashes.Add(jointHash);
            
            // Match by joint name directly (animation data is keyed by node name)
            var translations = nodeKeyframes.GetValueOrDefault(jointName)?.GetValueOrDefault("translation");
            var rotations = nodeRotations.GetValueOrDefault(jointName)?.GetValueOrDefault("rotation");
            var scales = nodeScales.GetValueOrDefault(jointName)?.GetValueOrDefault("scale");
            
            bool hasAnimation = translations != null || rotations != null || scales != null || 
                                translationCurveSamplers.ContainsKey(jointName) || 
                                rotationCurveSamplers.ContainsKey(jointName) || 
                                scaleCurveSamplers.ContainsKey(jointName);
            if (hasAnimation)
                jointsWithAnimation++;
            
            List<(ushort, ushort, ushort)> frames = new();
            
            // Sample frames exactly like CreateGltfAnimation: frameTime = frameId * frameDuration
            // Use curve samplers for proper evaluation (fixes micro stutters)
            for (int frameId = 0; frameId < frameCount; frameId++)
            {
                // Calculate frameTime with exact precision to avoid floating point errors
                // frameDuration = 1/30 = 0.033333... - use exact calculation
                float frameTime = (float)frameId / fps; // More precise than frameId * frameDuration
                
                // Evaluate using curve samplers if available (proper interpolation)
                System.Numerics.Vector3 translation = System.Numerics.Vector3.Zero;
                System.Numerics.Quaternion rotation = System.Numerics.Quaternion.Identity;
                System.Numerics.Vector3 scale = System.Numerics.Vector3.One;
                
                // Use curve sampler if available (proper interpolation), otherwise fall back to manual interpolation
                bool usedCurveSamplerTrans = false;
                bool usedCurveSamplerRot = false;
                bool usedCurveSamplerScale = false;
                
                if (translationCurveSamplers.TryGetValue(jointName, out var transSampler))
                {
                    try
                    {
                        // Try ICurveSampler<Vector3>.GetPoint(float)
                        var curveSamplerInterface = typeof(SharpGLTF.Animations.ICurveSampler<>).MakeGenericType(typeof(System.Numerics.Vector3));
                        if (curveSamplerInterface.IsAssignableFrom(transSampler.GetType()))
                        {
                            var getPointMethod = curveSamplerInterface.GetMethod("GetPoint", new[] { typeof(float) });
                            if (getPointMethod != null)
                            {
                                translation = (System.Numerics.Vector3)getPointMethod.Invoke(transSampler, new object[] { frameTime });
                                usedCurveSamplerTrans = true;
                            }
                        }
                    }
                    catch (Exception ex)
                    {
                        if (frameId == 0 && jointIdx == 0) // Only log once
                            Console.WriteLine($"[ANM Export] DEBUG: Translation curve sampler failed for '{jointName}': {ex.Message}");
                    }
                }
                
                if (!usedCurveSamplerTrans && translations != null)
                {
                    // Check if all keyframes have the same value (static/constant animation)
                    if (translations.Count > 0)
                    {
                        var firstValue = translations[0].value;
                        bool isConstant = translations.All(kf => 
                            Math.Abs(kf.value.X - firstValue.X) < 0.0001f &&
                            Math.Abs(kf.value.Y - firstValue.Y) < 0.0001f &&
                            Math.Abs(kf.value.Z - firstValue.Z) < 0.0001f);
                        
                        if (isConstant)
                        {
                            // Use constant value directly - no interpolation needed
                            translation = firstValue;
                        }
                        else
                        {
                            // Actually animated - use interpolation
                            translation = InterpolateVector3(translations, frameTime) ?? System.Numerics.Vector3.Zero;
                        }
                    }
                    else
                    {
                        translation = System.Numerics.Vector3.Zero;
                    }
                }
                
                if (rotationCurveSamplers.TryGetValue(jointName, out var rotSampler))
                {
                    try
                    {
                        // Try ICurveSampler<Quaternion>.GetPoint(float)
                        var curveSamplerInterface = typeof(SharpGLTF.Animations.ICurveSampler<>).MakeGenericType(typeof(System.Numerics.Quaternion));
                        if (curveSamplerInterface.IsAssignableFrom(rotSampler.GetType()))
                        {
                            var getPointMethod = curveSamplerInterface.GetMethod("GetPoint", new[] { typeof(float) });
                            if (getPointMethod != null)
                            {
                                rotation = (System.Numerics.Quaternion)getPointMethod.Invoke(rotSampler, new object[] { frameTime });
                                usedCurveSamplerRot = true;
                            }
                        }
                    }
                    catch (Exception ex)
                    {
                        if (frameId == 0 && jointIdx == 0) // Only log once
                            Console.WriteLine($"[ANM Export] DEBUG: Rotation curve sampler failed for '{jointName}': {ex.Message}");
                    }
                }
                
                if (!usedCurveSamplerRot && rotations != null)
                {
                    // Check if all keyframes have the same value (static/constant animation)
                    if (rotations.Count > 0)
                    {
                        var firstValue = rotations[0].value;
                        bool isConstant = rotations.All(kf => 
                            Math.Abs(kf.value.X - firstValue.X) < 0.0001f &&
                            Math.Abs(kf.value.Y - firstValue.Y) < 0.0001f &&
                            Math.Abs(kf.value.Z - firstValue.Z) < 0.0001f &&
                            Math.Abs(kf.value.W - firstValue.W) < 0.0001f);
                        
                        if (isConstant)
                        {
                            // Use constant value directly - no interpolation needed
                            rotation = firstValue;
                        }
                        else
                        {
                            // Actually animated - use interpolation
                            rotation = InterpolateQuaternion(rotations, frameTime) ?? System.Numerics.Quaternion.Identity;
                        }
                    }
                    else
                    {
                        rotation = System.Numerics.Quaternion.Identity;
                    }
                }
                
                if (scaleCurveSamplers.TryGetValue(jointName, out var scaleSampler))
                {
                    try
                    {
                        // Try ICurveSampler<Vector3>.GetPoint(float)
                        var curveSamplerInterface = typeof(SharpGLTF.Animations.ICurveSampler<>).MakeGenericType(typeof(System.Numerics.Vector3));
                        if (curveSamplerInterface.IsAssignableFrom(scaleSampler.GetType()))
                        {
                            var getPointMethod = curveSamplerInterface.GetMethod("GetPoint", new[] { typeof(float) });
                            if (getPointMethod != null)
                            {
                                scale = (System.Numerics.Vector3)getPointMethod.Invoke(scaleSampler, new object[] { frameTime });
                                usedCurveSamplerScale = true;
                            }
                        }
                    }
                    catch (Exception ex)
                    {
                        if (frameId == 0 && jointIdx == 0) // Only log once
                            Console.WriteLine($"[ANM Export] DEBUG: Scale curve sampler failed for '{jointName}': {ex.Message}");
                    }
                }
                
                if (!usedCurveSamplerScale && scales != null)
                {
                    // Check if all keyframes have the same value (static/constant animation)
                    if (scales.Count > 0)
                    {
                        var firstValue = scales[0].value;
                        bool isConstant = scales.All(kf => 
                            Math.Abs(kf.value.X - firstValue.X) < 0.0001f &&
                            Math.Abs(kf.value.Y - firstValue.Y) < 0.0001f &&
                            Math.Abs(kf.value.Z - firstValue.Z) < 0.0001f);
                        
                        if (isConstant)
                        {
                            // Use constant value directly - no interpolation needed
                            scale = firstValue;
                        }
                        else
                        {
                            // Actually animated - use interpolation
                            scale = InterpolateVector3(scales, frameTime) ?? System.Numerics.Vector3.One;
                        }
                    }
                    else
                    {
                        scale = System.Numerics.Vector3.One;
                    }
                }
                
                // Track if this joint uses curve samplers (only count once per joint)
                if (frameId == 0)
                {
                    bool usesAnyCurveSampler = usedCurveSamplerTrans || usedCurveSamplerRot || usedCurveSamplerScale;
                    if (usesAnyCurveSampler)
                    {
                        jointsUsingCurveSamplers++;
                    }
                    else if (hasAnimation)
                    {
                        // This joint has animation but is not using curve samplers
                        string missingTypes = "";
                        if (translations != null && !usedCurveSamplerTrans) missingTypes += "translation ";
                        if (rotations != null && !usedCurveSamplerRot) missingTypes += "rotation ";
                        if (scales != null && !usedCurveSamplerScale) missingTypes += "scale ";
                        jointsNotUsingCurveSamplers.Add($"{jointName} (missing: {missingTypes.Trim()})");
                    }
                }
                
                // Normalize values to reduce floating point precision issues that cause stuttering
                // Round to reasonable precision to avoid duplicate palette entries from tiny variations
                translation = new System.Numerics.Vector3(
                    (float)Math.Round(translation.X, 6),
                    (float)Math.Round(translation.Y, 6),
                    (float)Math.Round(translation.Z, 6)
                );
                scale = new System.Numerics.Vector3(
                    (float)Math.Round(scale.X, 6),
                    (float)Math.Round(scale.Y, 6),
                    (float)Math.Round(scale.Z, 6)
                );
                // Normalize quaternion to ensure consistent representation
                rotation = System.Numerics.Quaternion.Normalize(rotation);
                
                // Add to palettes and get indices
                int transIdx = AddToPalette(vectorPalette, translation);
                int scaleIdx = AddToPalette(vectorPalette, scale);
                int rotIdx = AddToPalette(quatPalette, rotation);
                
                // Check for overflow (ushort max is 65535)
                if (transIdx > ushort.MaxValue || scaleIdx > ushort.MaxValue || rotIdx > ushort.MaxValue)
                {
                    throw new InvalidOperationException($"Palette index overflow: translation={transIdx}, scale={scaleIdx}, rotation={rotIdx}. Palette sizes: vectors={vectorPalette.Count}, quaternions={quatPalette.Count}");
                }
                
                ushort translationId = (ushort)transIdx;
                ushort scaleId = (ushort)scaleIdx;
                ushort rotationId = (ushort)rotIdx;
                
                frames.Add((translationId, scaleId, rotationId));
            }
            
            allJointFrames.Add(frames);
        }
        
        Console.WriteLine($"[ANM Export] {jointsWithAnimation}/{jointNames.Count} joints have animation data");
        Console.WriteLine($"[ANM Export] {jointsUsingCurveSamplers}/{jointNames.Count} joints using curve samplers (smooth interpolation)");
        
        if (jointsNotUsingCurveSamplers.Count > 0)
        {
            Console.WriteLine($"[ANM Export] WARNING: {jointsNotUsingCurveSamplers.Count} joints NOT using curve samplers (will use manual interpolation):");
            foreach (var jointInfo in jointsNotUsingCurveSamplers.Take(20)) // Show first 20
            {
                Console.WriteLine($"[ANM Export]   - {jointInfo}");
            }
            if (jointsNotUsingCurveSamplers.Count > 20)
            {
                Console.WriteLine($"[ANM Export]   ... and {jointsNotUsingCurveSamplers.Count - 20} more");
            }
        }
        
        Console.WriteLine($"[ANM Export] Vector palette size: {vectorPalette.Count}, Quaternion palette size: {quatPalette.Count}");
        
        // Check palette sizes before writing
        if (vectorPalette.Count > ushort.MaxValue)
        {
            throw new InvalidOperationException($"Vector palette too large: {vectorPalette.Count} entries (max {ushort.MaxValue})");
        }
        if (quatPalette.Count > ushort.MaxValue)
        {
            throw new InvalidOperationException($"Quaternion palette too large: {quatPalette.Count} entries (max {ushort.MaxValue})");
        }
        
        // Calculate the base offset (after header: 8 bytes magic + 4 bytes version + 4 bytes resourceSize = 16 bytes)
        // Then: 4 bytes formatToken + 4 bytes version + 4 bytes flags + 4 bytes trackCount + 4 bytes frameCount + 4 bytes frameDuration + 6*4 bytes offsets = 48 bytes
        // Total header = 16 + 48 = 64 bytes
        const long headerSize = 64;
        long currentOffset = headerSize;
        
        // Write sections in the correct order for V5:
        // 1. Vector palette (first)
        // Offset points to where padding starts (ReadV5 seeks to offset + 12)
        long vectorPaletteOffset = currentOffset;
        bw.BaseStream.Position = currentOffset;
        // Write 12 bytes padding (resource header padding)
        bw.Write(0);
        bw.Write(0);
        bw.Write(0);
        foreach (var vec in vectorPalette)
        {
            bw.Write(vec.X);
            bw.Write(vec.Y);
            bw.Write(vec.Z);
        }
        currentOffset = bw.BaseStream.Position;
        
        // 2. Quaternion palette (second)
        // Offset points to where padding starts (ReadV5 seeks to offset + 12)
        long quatPaletteOffset = currentOffset;
        bw.BaseStream.Position = currentOffset;
        // Write 12 bytes padding
        bw.Write(0);
        bw.Write(0);
        bw.Write(0);
        
        // Compress quaternions using QuantizedQuaternion algorithm
        Span<byte> quantized = stackalloc byte[6];
        foreach (var quat in quatPalette)
        {
            CompressQuaternionToSpan(quat, quantized);
            bw.Write(quantized);
        }
        currentOffset = bw.BaseStream.Position;
        
        // 3. Joint hashes (third)
        // Offset points to where padding starts (ReadV5 seeks to offset + 12)
        long jointHashesOffset = currentOffset;
        bw.BaseStream.Position = currentOffset;
        // Write 12 bytes padding
        bw.Write(0);
        bw.Write(0);
        bw.Write(0);
        foreach (uint jointHash in jointHashes)
        {
            bw.Write(jointHash);
        }
        currentOffset = bw.BaseStream.Position;
        
        // 4. Frames (last)
        // Offset points to where padding starts (ReadV5 seeks to offset + 12)
        long framesOffset = currentOffset;
        bw.BaseStream.Position = currentOffset;
        // Write 12 bytes padding
        bw.Write(0);
        bw.Write(0);
        bw.Write(0);
        
        // Write frames: for each frame, for each joint (in order)
        for (int frameId = 0; frameId < frameCount; frameId++)
        {
            for (int jointIdx = 0; jointIdx < jointNames.Count; jointIdx++)
            {
                var frames = allJointFrames[jointIdx];
                    var frame = frames[frameId];
                    bw.Write(frame.translationId);
                    bw.Write(frame.scaleId);
                    bw.Write(frame.rotationId);
                }
        }
        currentOffset = bw.BaseStream.Position;
        
        // Asset name and time offsets (not used in V5 but required)
        // Calculate them as placeholders
        long assetNameOffset = 0; // Not used in V5
        long timeOffset = 0; // Not used in V5
        
        // Write offsets back to the header
        // Offsets are relative to the start of the resource data (after 16-byte header)
        // But ReadV5 adds 12 bytes when seeking, so offsets should be absolute positions
        // Actually, looking at ReadV5: it seeks to offset + 12, so offsets are stored as absolute positions
        // But we need to account for the fact that offsets are stored as int32
        
        // Check for offset overflow (ANM format uses int32 for offsets)
        if (jointHashesOffset > int.MaxValue || assetNameOffset > int.MaxValue || 
            timeOffset > int.MaxValue || vectorPaletteOffset > int.MaxValue || 
            quatPaletteOffset > int.MaxValue || framesOffset > int.MaxValue)
        {
            throw new InvalidOperationException($"Offset overflow: jointHashes={jointHashesOffset}, assetName={assetNameOffset}, time={timeOffset}, vectorPalette={vectorPaletteOffset}, quatPalette={quatPaletteOffset}, frames={framesOffset}. File too large for ANM format.");
        }
        
        if (currentOffset > uint.MaxValue)
        {
            throw new InvalidOperationException($"Resource size overflow: currentPos={currentOffset} exceeds uint.MaxValue. File too large for ANM format.");
        }
        
        // Write offsets (as int32, relative to start of file)
        bw.BaseStream.Position = offsetsPos;
        bw.Write((int)jointHashesOffset);
        bw.Write((int)assetNameOffset);
        bw.Write((int)timeOffset);
        bw.Write((int)vectorPaletteOffset);
        bw.Write((int)quatPaletteOffset);
        bw.Write((int)framesOffset);
        
        // Write resource size (size of resource data section, from after header to end)
        uint resourceSize = (uint)(currentOffset - 16); // Subtract the 16-byte header
        bw.BaseStream.Position = resourceSizePos;
        bw.Write(resourceSize);
        
        // Ensure we're at the end
        bw.BaseStream.Position = currentOffset;
        
        Console.WriteLine($"[ANM Export] Successfully wrote ANM file:");
        Console.WriteLine($"[ANM Export]   - File size: {currentOffset} bytes");
        Console.WriteLine($"[ANM Export]   - Vector palette: {vectorPalette.Count} entries at offset {vectorPaletteOffset}");
        Console.WriteLine($"[ANM Export]   - Quaternion palette: {quatPalette.Count} entries at offset {quatPaletteOffset}");
        Console.WriteLine($"[ANM Export]   - Joint hashes: {jointHashes.Count} entries at offset {jointHashesOffset}");
        Console.WriteLine($"[ANM Export]   - Frames: {frameCount} frames x {jointNames.Count} joints at offset {framesOffset}");
    }
    
    private static int AddToPalette(List<System.Numerics.Vector3> palette, System.Numerics.Vector3 value)
    {
        // Use tighter tolerance to catch more duplicates (reduces palette size and stuttering)
        const float tolerance = 0.00001f; // Tighter than before
        for (int i = 0; i < palette.Count; i++)
        {
            if (System.Numerics.Vector3.DistanceSquared(palette[i], value) < tolerance)
                return i;
        }
        int index = palette.Count;
        palette.Add(value);
        return index;
    }
    
    private static int AddToPalette(List<System.Numerics.Quaternion> palette, System.Numerics.Quaternion value)
    {
        // Normalize to ensure consistent representation
        value = System.Numerics.Quaternion.Normalize(value);
        
        // Use tighter tolerance to catch more duplicates
        for (int i = 0; i < palette.Count; i++)
        {
            // Check if quaternions represent the same rotation (accounting for q == -q)
            float dot = System.Math.Abs(System.Numerics.Quaternion.Dot(palette[i], value));
            if (dot > 0.99999f) // Tighter tolerance - very close quaternions
                return i;
        }
        int index = palette.Count;
        palette.Add(value);
        return index;
    }
    
    private static void CompressQuaternionToSpan(System.Numerics.Quaternion quat, Span<byte> compressed)
    {
        // Implementation based on LeagueToolkit.Core.Primitives.QuantizedQuaternion.Compress
        const double SQRT_2 = 1.41421356237;
        
        // Normalize quaternion to ensure it's valid
        if (float.IsNaN(quat.X) || float.IsNaN(quat.Y) || float.IsNaN(quat.Z) || float.IsNaN(quat.W))
        {
            quat = System.Numerics.Quaternion.Identity;
        }
        else
        {
            quat = System.Numerics.Quaternion.Normalize(quat);
        }
        
        uint maxIndex = 3;
        float x_abs = Math.Abs(quat.X);
        float y_abs = Math.Abs(quat.Y);
        float z_abs = Math.Abs(quat.Z);
        float w_abs = Math.Abs(quat.W);
        
        if (x_abs >= w_abs && x_abs >= y_abs && x_abs >= z_abs)
        {
            maxIndex = 0;
            if (quat.X < 0f)
                quat *= -1;
        }
        else if (y_abs >= w_abs && y_abs >= x_abs && y_abs >= z_abs)
        {
            maxIndex = 1;
            if (quat.Y < 0f)
                quat *= -1;
        }
        else if (z_abs >= w_abs && z_abs >= x_abs && z_abs >= y_abs)
        {
            maxIndex = 2;
            if (quat.Z < 0f)
                quat *= -1;
        }
        else if (quat.W < 0f)
        {
            quat *= -1;
        }
        
        Span<float> components = stackalloc float[] { quat.X, quat.Y, quat.Z, quat.W };
        ulong bits = (ulong)maxIndex << 45;
        for (int i = 0, compressedIndex = 0; i < 4; i++)
        {
            if (i == maxIndex)
                continue;
            
            ushort component = (ushort)Math.Round(32767.0 / 2.0 * (SQRT_2 * components[i] + 1.0));
            bits |= (ulong)(component & 0b0111_1111_1111_1111) << (15 * (2 - compressedIndex));
            
            compressedIndex++;
        }
        
        for (int i = 0; i < 6; i++)
        {
            compressed[i] = (byte)((bits >> (8 * i)) & 0b1111_1111);
        }
    }

    private static object CreateAnimationTrack(string jointName, int nodeIndex, int frameCount, float frameDuration, float fps,
        Dictionary<string, List<(float time, System.Numerics.Vector3 value)>> translations,
        Dictionary<string, List<(float time, System.Numerics.Quaternion value)>> rotations,
        Dictionary<string, List<(float time, System.Numerics.Vector3 value)>> scales)
    {
        // Get the AnimationTrack type from LeagueToolkit
        var trackType = typeof(IAnimationAsset).Assembly.GetTypes()
            .FirstOrDefault(t => t.Name == "AnimationTrack" || (t.Name.Contains("Track") && t.GetInterfaces().Any()));

        if (trackType == null)
        {
            // Try to find it in LeagueToolkit.Core.Animation
            var coreAnimation = typeof(IAnimationAsset).Assembly;
            trackType = coreAnimation.GetTypes()
                .FirstOrDefault(t => t.Namespace == "LeagueToolkit.Core.Animation" && t.Name.Contains("Track"));
        }

        if (trackType == null)
            return null;

        var track = Activator.CreateInstance(trackType);

        // Create keyframes for each frame
        var keyframesProperty = trackType.GetProperty("Keyframes") ?? trackType.GetProperty("Frames");
        if (keyframesProperty != null)
        {
            var keyframesList = Activator.CreateInstance(keyframesProperty.PropertyType);
            var addMethod = keyframesProperty.PropertyType.GetMethod("Add");

            for (int frame = 0; frame < frameCount; frame++)
            {
                float time = frame * frameDuration;

                // Get translation, rotation, scale for this frame
                var translation = InterpolateVector3(translations?.GetValueOrDefault("translation"), time) ?? System.Numerics.Vector3.Zero;
                var rotation = InterpolateQuaternion(rotations?.GetValueOrDefault("rotation"), time) ?? System.Numerics.Quaternion.Identity;
                var scale = InterpolateVector3(scales?.GetValueOrDefault("scale"), time) ?? System.Numerics.Vector3.One;

                // Create keyframe
                var keyframe = CreateKeyframe(translation, rotation, scale);
                if (keyframe != null && addMethod != null)
                {
                    addMethod.Invoke(keyframesList, new object[] { keyframe });
                }
            }

            keyframesProperty.SetValue(track, keyframesList);
        }

        return track;
    }

    private static object CreateKeyframe(System.Numerics.Vector3 translation, System.Numerics.Quaternion rotation, System.Numerics.Vector3 scale)
    {
        // Find AnimationKeyframe type
        var keyframeType = typeof(IAnimationAsset).Assembly.GetTypes()
            .FirstOrDefault(t => t.Name.Contains("Keyframe") && t.Namespace?.Contains("Animation") == true);

        if (keyframeType == null)
            return null;

        var keyframe = Activator.CreateInstance(keyframeType);

        // Set properties
        var transProp = keyframeType.GetProperty("Translation");
        var rotProp = keyframeType.GetProperty("Rotation");
        var scaleProp = keyframeType.GetProperty("Scale");

        if (transProp != null)
            transProp.SetValue(keyframe, translation);
        if (rotProp != null)
            rotProp.SetValue(keyframe, rotation);
        if (scaleProp != null)
            scaleProp.SetValue(keyframe, scale);

        return keyframe;
    }

    private static System.Numerics.Vector3? InterpolateVector3(List<(float time, System.Numerics.Vector3 value)> keyframes, float time)
    {
        if (keyframes == null || keyframes.Count == 0)
            return null;

        if (keyframes.Count == 1)
            return keyframes[0].value;

        // Handle time before first keyframe
        if (time <= keyframes[0].time)
            return keyframes[0].value;

        // Handle time after last keyframe
        if (time >= keyframes[keyframes.Count - 1].time)
            return keyframes[keyframes.Count - 1].value;

        // Find surrounding keyframes using binary search for better performance
        int left = 0;
        int right = keyframes.Count - 1;
        int index = 0;

        while (left <= right)
        {
            int mid = (left + right) / 2;
            if (keyframes[mid].time <= time && (mid == keyframes.Count - 1 || keyframes[mid + 1].time > time))
            {
                index = mid;
                break;
            }
            else if (keyframes[mid].time < time)
            {
                left = mid + 1;
            }
            else
            {
                right = mid - 1;
            }
        }

        // Ensure we have a valid pair
        if (index >= keyframes.Count - 1)
            return keyframes[keyframes.Count - 1].value;

        var kf1 = keyframes[index];
        var kf2 = keyframes[index + 1];

        // Calculate interpolation factor with proper clamping
        float deltaTime = kf2.time - kf1.time;
        if (deltaTime < 0.0001f) // Avoid division by zero
            return kf1.value;

        float t = Math.Max(0f, Math.Min(1f, (time - kf1.time) / deltaTime));
        return System.Numerics.Vector3.Lerp(kf1.value, kf2.value, t);
    }

    private static System.Numerics.Quaternion? InterpolateQuaternion(List<(float time, System.Numerics.Quaternion value)> keyframes, float time)
    {
        if (keyframes == null || keyframes.Count == 0)
            return null;

        if (keyframes.Count == 1)
            return keyframes[0].value;

        // Handle time before first keyframe
        if (time <= keyframes[0].time)
            return keyframes[0].value;

        // Handle time after last keyframe
        if (time >= keyframes[keyframes.Count - 1].time)
            return keyframes[keyframes.Count - 1].value;

        // Find surrounding keyframes using binary search for better performance
        int left = 0;
        int right = keyframes.Count - 1;
        int index = 0;

        while (left <= right)
        {
            int mid = (left + right) / 2;
            if (keyframes[mid].time <= time && (mid == keyframes.Count - 1 || keyframes[mid + 1].time > time))
            {
                index = mid;
                break;
            }
            else if (keyframes[mid].time < time)
            {
                left = mid + 1;
            }
            else
            {
                right = mid - 1;
            }
        }

        // Ensure we have a valid pair
        if (index >= keyframes.Count - 1)
            return keyframes[keyframes.Count - 1].value;

        var kf1 = keyframes[index];
        var kf2 = keyframes[index + 1];

        // Calculate interpolation factor with proper clamping
        float deltaTime = kf2.time - kf1.time;
        if (deltaTime < 0.0001f) // Avoid division by zero
            return kf1.value;

        float t = Math.Max(0f, Math.Min(1f, (time - kf1.time) / deltaTime));
        // Use Lerp instead of Slerp to match LeagueToolkit's Evaluate method exactly
        // LeagueToolkit uses Quaternion.Lerp in UncompressedAnimationAsset.EvaluateWithInterpolation
        return System.Numerics.Quaternion.Lerp(kf1.value, kf2.value, t);
    }

    private static uint GetJointHash(string jointName)
    {
        // LeagueToolkit uses ELF hash for joint names
        // Try to use LeagueToolkit's hash function if available
        try
        {
            var hashType = typeof(IAnimationAsset).Assembly.GetType("LeagueToolkit.Hashing.Elf");
            if (hashType != null)
            {
                var hashMethod = hashType.GetMethod("HashLower", new[] { typeof(string) });
                if (hashMethod != null && hashMethod.IsStatic)
                {
                    var result = hashMethod.Invoke(null, new object[] { jointName });
                    if (result is uint u)
                        return u;
                    if (result is int i)
                        return (uint)i;
                }
            }
        }
        catch
        {
            // Fall through to fallback
        }

        // Fallback: ELF hash implementation
        uint hash = 0;
        foreach (char c in jointName.ToLowerInvariant())
        {
            hash = ((hash << 4) + (uint)c) ^ (hash >> 28);
        }
        return hash;
    }

    private static IEnumerable<(string, IAnimationAsset)> LoadAnimations(string path) =>
        Directory
            .EnumerateFiles(path, "*.anm")
            .Select(animationPath =>
            {
                using FileStream stream = File.OpenRead(animationPath);
                return (Path.GetFileNameWithoutExtension(animationPath), AnimationAsset.Load(stream));
            });

    private static void ApplyAutomaticBoneOrientation(ModelRoot gltf)
    {
        Console.WriteLine("[lol2gltf] ===== Starting Automatic Bone Orientation =====");
        
        // Find skin (should have exactly one for skinned meshes)
        var skins = gltf.LogicalSkins?.ToList();
        Console.WriteLine($"[lol2gltf] Found {skins?.Count ?? 0} skin(s) in glTF");
        
        var skin = skins?.FirstOrDefault();
        if (skin == null)
        {
            Console.WriteLine("[lol2gltf] ERROR: No skin found, skipping automatic bone orientation");
            return;
        }
        
        Console.WriteLine($"[lol2gltf] Using skin with {skin.JointsCount} joints");
        
        if (skin.JointsCount == 0)
        {
            Console.WriteLine("[lol2gltf] ERROR: Skin has 0 joints, skipping automatic bone orientation");
            return;
        }

        Console.WriteLine($"[lol2gltf] Applying automatic bone orientation to {skin.JointsCount} joints");

        // Build bone hierarchy (parent -> children map)
        var boneChildrenMap = new Dictionary<int, List<int>>();
        var jointNodes = skin.Joints.ToList();
        Console.WriteLine($"[lol2gltf] Building bone hierarchy from {jointNodes.Count} joint nodes");
        
        int bonesWithChildren = 0;
        for (int i = 0; i < jointNodes.Count; i++)
        {
            var node = jointNodes[i];
            var visualChildren = node.VisualChildren;
            if (visualChildren != null && visualChildren.Any())
            {
                var childList = new List<int>();
                foreach (var child in visualChildren)
                {
                    int childIndex = jointNodes.IndexOf(child);
                    if (childIndex >= 0)
                    {
                        childList.Add(childIndex);
                    }
                }
                if (childList.Count > 0)
                {
                    boneChildrenMap[i] = childList;
                    bonesWithChildren++;
                    Console.WriteLine($"[lol2gltf] Bone {i} ({node.Name}) has {childList.Count} child joint(s)");
                }
            }
        }
        Console.WriteLine($"[lol2gltf] Found {bonesWithChildren} bones with children out of {jointNodes.Count} total bones");

        // Store correction matrices for each bone
        var boneCorrectionMatrices = new Dictionary<int, System.Numerics.Matrix4x4?>();

        // Helper function to find best axis from direction vector (FBX algorithm)
        System.Numerics.Vector3 FindBestAxisFromVector(System.Numerics.Vector3 vec)
        {
            System.Numerics.Vector3 bestAxis = new System.Numerics.Vector3(0, 0, vec.Z >= 0 ? 1 : -1);
            if (Math.Abs(vec.X) > Math.Abs(vec.Y))
            {
                if (Math.Abs(vec.X) > Math.Abs(vec.Z))
                {
                    bestAxis = new System.Numerics.Vector3(vec.X >= 0 ? 1 : -1, 0, 0);
                }
            }
            else if (Math.Abs(vec.Y) > Math.Abs(vec.Z))
            {
                bestAxis = new System.Numerics.Vector3(0, vec.Y >= 0 ? 1 : -1, 0);
            }
            return bestAxis;
        }

        // Helper function to find best axis from multiple child directions (FBX algorithm)
        System.Numerics.Vector3 FindBestAxisFromChildren(List<System.Numerics.Vector3> childDirs)
        {
            float bestAngle = -1.0f;
            System.Numerics.Vector3 bestAxis = new System.Numerics.Vector3(1, 0, 0);

            foreach (var vec in childDirs)
            {
                var testAxis = FindBestAxisFromVector(vec);

                // Find max angle to children
                float maxAngle = 1.0f;
                foreach (var loc in childDirs)
                {
                    maxAngle = Math.Min(maxAngle, System.Numerics.Vector3.Dot(testAxis, loc));
                }

                // Is it better than the last one?
                if (bestAngle < maxAngle)
                {
                    bestAngle = maxAngle;
                    bestAxis = testAxis;
                }
            }

            return bestAxis;
        }

        // Helper function to convert axis to strings (FBX algorithm)
        (string toUp, string toForward) AxisToStrings(System.Numerics.Vector3 axis)
        {
            string toUp = axis.Z >= 0 ? "Z" : "-Z";
            if (Math.Abs(axis.X) > Math.Abs(axis.Y))
            {
                if (Math.Abs(axis.X) > Math.Abs(axis.Z))
                {
                    toUp = axis.X >= 0 ? "X" : "-X";
                }
            }
            else if (Math.Abs(axis.Y) > Math.Abs(axis.Z))
            {
                toUp = axis.Y >= 0 ? "Y" : "-Y";
            }
            string toForward = (toUp != "X" && toUp != "-X") ? "X" : "Y";
            return (toUp, toForward);
        }

        // Helper function to get child direction vector
        System.Numerics.Vector3 GetChildDirection(SharpGLTF.Schema2.Node parentNode, SharpGLTF.Schema2.Node childNode)
        {
            var parentWorld = parentNode.WorldMatrix;
            var childWorld = childNode.WorldMatrix;
            
            var parentPos = new System.Numerics.Vector3(parentWorld.M41, parentWorld.M42, parentWorld.M43);
            var childPos = new System.Numerics.Vector3(childWorld.M41, childWorld.M42, childWorld.M43);
            
            var dir = childPos - parentPos;
            if (dir.Length() > 0.0001f)
            {
                return System.Numerics.Vector3.Normalize(dir);
            }
            return new System.Numerics.Vector3(0, 0, 1);
        }

        // Helper function to create axis conversion matrix
        System.Numerics.Matrix4x4 CreateAxisConversionMatrix(string fromForward, string fromUp, string toForward, string toUp)
        {
            // Map axis strings to vectors
            System.Numerics.Vector3 GetAxisVector(string axis)
            {
                return axis switch
                {
                    "X" => new System.Numerics.Vector3(1, 0, 0),
                    "-X" => new System.Numerics.Vector3(-1, 0, 0),
                    "Y" => new System.Numerics.Vector3(0, 1, 0),
                    "-Y" => new System.Numerics.Vector3(0, -1, 0),
                    "Z" => new System.Numerics.Vector3(0, 0, 1),
                    "-Z" => new System.Numerics.Vector3(0, 0, -1),
                    _ => new System.Numerics.Vector3(1, 0, 0)
                };
            }

            var fromF = GetAxisVector(fromForward);
            var fromU = GetAxisVector(fromUp);
            var toF = GetAxisVector(toForward);
            var toU = GetAxisVector(toUp);

            // Calculate right vectors
            var fromR = System.Numerics.Vector3.Cross(fromU, fromF);
            var toR = System.Numerics.Vector3.Cross(toU, toF);

            // Build rotation matrix
            var rot = new System.Numerics.Matrix4x4(
                toR.X, toR.Y, toR.Z, 0,
                toU.X, toU.Y, toU.Z, 0,
                toF.X, toF.Y, toF.Z, 0,
                0, 0, 0, 1
            );

            var fromInv = new System.Numerics.Matrix4x4(
                fromR.X, fromU.X, fromF.X, 0,
                fromR.Y, fromU.Y, fromF.Y, 0,
                fromR.Z, fromU.Z, fromF.Z, 0,
                0, 0, 0, 1
            );

            return rot * fromInv;
        }

        // Find bone correction matrix (FBX algorithm)
        System.Numerics.Matrix4x4? FindBoneCorrectionMatrix(int jointIdx)
        {
            if (boneCorrectionMatrices.ContainsKey(jointIdx))
            {
                return boneCorrectionMatrices[jointIdx];
            }

            var node = jointNodes[jointIdx];
            System.Numerics.Matrix4x4? correctionMatrix = null;

            // Get bone children
            var boneChildren = boneChildrenMap.ContainsKey(jointIdx) ? boneChildrenMap[jointIdx] : new List<int>();

            if (boneChildren.Count == 0)
            {
                // No children: inherit correction from parent if possible
                var parent = node.VisualParent;
                if (parent != null)
                {
                    int parentIdx = jointNodes.IndexOf(parent);
                    if (parentIdx >= 0)
                    {
                        Console.WriteLine($"[lol2gltf] Bone {jointIdx} ({node.Name}) has no children, inheriting from parent {parentIdx}");
                        var parentCorr = FindBoneCorrectionMatrix(parentIdx);
                        if (parentCorr.HasValue)
                        {
                            correctionMatrix = parentCorr.Value;
                            Console.WriteLine($"[lol2gltf] Bone {jointIdx} inherited correction matrix from parent");
                        }
                    }
                }
                else
                {
                    Console.WriteLine($"[lol2gltf] Bone {jointIdx} ({node.Name}) has no children and no parent, no correction needed");
                }
            }
            else
            {
                // Find best orientation to align bone with children (FBX logic)
                System.Numerics.Vector3 bestAxis;

                if (boneChildren.Count == 1)
                {
                    // Single child: use its direction
                    var childNode = jointNodes[boneChildren[0]];
                    var vec = GetChildDirection(node, childNode);
                    Console.WriteLine($"[lol2gltf] Bone {jointIdx} ({node.Name}) has 1 child, direction vector: ({vec.X:F4}, {vec.Y:F4}, {vec.Z:F4})");
                    bestAxis = FindBestAxisFromVector(vec);
                }
                else
                {
                    // Multiple children: find best axis
                    var childDirs = new List<System.Numerics.Vector3>();
                    foreach (var childIdx in boneChildren)
                    {
                        var childNode = jointNodes[childIdx];
                        var vec = GetChildDirection(node, childNode);
                        childDirs.Add(vec);
                    }

                    if (childDirs.Count > 0)
                    {
                        Console.WriteLine($"[lol2gltf] Bone {jointIdx} ({node.Name}) has {boneChildren.Count} children, finding best axis");
                        bestAxis = FindBestAxisFromChildren(childDirs);
                    }
                    else
                    {
                        bestAxis = new System.Numerics.Vector3(1, 0, 0);
                    }
                }

                // Convert to axis strings
                var (toUp, toForward) = AxisToStrings(bestAxis);
                Console.WriteLine($"[lol2gltf] Bone {jointIdx} ({node.Name}) best axis: up={toUp}, forward={toForward}");

                // Build correction matrix
                if (toUp != "Y" || toForward != "X")
                {
                    correctionMatrix = CreateAxisConversionMatrix("X", "Y", toForward, toUp);
                    Console.WriteLine($"[lol2gltf] Bone {jointIdx} ({node.Name}) created correction matrix (from X/Y to {toForward}/{toUp})");
                }
                else
                {
                    Console.WriteLine($"[lol2gltf] Bone {jointIdx} ({node.Name}) already aligned (Y-up, X-forward), no correction needed");
                }
            }

            boneCorrectionMatrices[jointIdx] = correctionMatrix;
            return correctionMatrix;
        }

        // Process all bones to find correction matrices (from root to leaves)
        var processed = new HashSet<int>();
        
        void ProcessBone(int jointIdx)
        {
            if (processed.Contains(jointIdx))
                return;

            // Process parent first
            var node = jointNodes[jointIdx];
            var parent = node.VisualParent;
            if (parent != null)
            {
                int parentIdx = jointNodes.IndexOf(parent);
                if (parentIdx >= 0 && !processed.Contains(parentIdx))
                {
                    ProcessBone(parentIdx);
                }
            }

            FindBoneCorrectionMatrix(jointIdx);
            processed.Add(jointIdx);
        }

        // Process all root bones first
        for (int i = 0; i < jointNodes.Count; i++)
        {
            if (jointNodes[i].VisualParent == null)
            {
                ProcessBone(i);
            }
        }

        // Process any remaining bones
        for (int i = 0; i < jointNodes.Count; i++)
        {
            if (!processed.Contains(i))
            {
                ProcessBone(i);
            }
        }

        int correctionCount = boneCorrectionMatrices.Values.Count(m => m.HasValue);
        Console.WriteLine($"[lol2gltf] Calculated {correctionCount} bone correction matrices out of {jointNodes.Count} total bones");

        // Step 1: Apply corrections to node transforms
        int appliedCount = 0;
        for (int i = 0; i < jointNodes.Count; i++)
        {
            var correctionMatrix = boneCorrectionMatrices.GetValueOrDefault(i);
            if (!correctionMatrix.HasValue)
                continue;

            var node = jointNodes[i];
            var localTransform = node.LocalTransform;
            var oldMatrix = localTransform.Matrix;

            // Apply correction to local transform
            var localMatrix = localTransform.Matrix;
            var correctedMatrix = localMatrix * correctionMatrix.Value;

            // Extract new transform (implicit conversion from Matrix4x4 to AffineTransform)
            node.LocalTransform = correctedMatrix;
            appliedCount++;
            
            Console.WriteLine($"[lol2gltf] Applied correction to bone {i} ({node.Name})");
        }

        Console.WriteLine($"[lol2gltf] Applied corrections to {appliedCount} node transforms");
        
        // After modifying node transforms, we need to update any accessors that reference them
        // This is especially important for vertex position accessors that might be affected
        // by the bone transform changes. However, since we're only modifying bone transforms
        // and not vertex positions, we mainly need to ensure inverse bind matrices are valid.

        // Step 2: Transform inverse bind matrices to account for bone corrections
        // When we apply a correction C to a bone's local transform, the world transform changes.
        // To maintain correct skinning, we need to transform the IBM.
        // Formula: If bone_world_new = bone_world_old @ C_world, then IBM_new = C_world_inv @ IBM_old
        // But since corrections are applied in local space, we need to compute the world-space correction
        var ibmAccessor = skin.GetInverseBindMatricesAccessor();
        if (ibmAccessor == null)
        {
            Console.WriteLine("[lol2gltf] WARNING: No inverse bind matrices accessor found, skipping IBM transformation");
        }
        else
        {
            Console.WriteLine($"[lol2gltf] Found inverse bind matrices accessor with {ibmAccessor.Count} matrices");
            
            // Read original IBMs
            var originalIbmArray = ibmAccessor.AsMatrix4x4Array();
            var ibmData = new Matrix4x4[originalIbmArray.Count];
            for (int i = 0; i < ibmData.Length; i++)
            {
                ibmData[i] = originalIbmArray[i];
            }
            Console.WriteLine($"[lol2gltf] Read {ibmData.Length} original inverse bind matrices");
            
            // Recalculate IBMs based on corrected bone world transforms
            // Formula: IBM = mesh_bind * inverse(joint_world)
            // We can derive mesh_bind from the original IBM: mesh_bind = IBM_old * joint_world_old
            // Then: IBM_new = (IBM_old * joint_world_old) * inverse(joint_world_new)
            int ibmRecalculated = 0;
            for (int i = 0; i < jointNodes.Count && i < ibmData.Length; i++)
            {
                var correctionMatrix = boneCorrectionMatrices.GetValueOrDefault(i);
                if (!correctionMatrix.HasValue)
                    continue;
                
                var node = jointNodes[i];
                var oldIbm = ibmData[i];
                
                // Get original world transform by temporarily reverting the correction
                var currentLocal = node.LocalTransform.Matrix;
                if (Matrix4x4.Invert(correctionMatrix.Value, out var correctionInv))
                {
                    var originalLocal = currentLocal * correctionInv;
                    var tempLocal = node.LocalTransform;
                    
                    // Get original world transform
                    node.LocalTransform = originalLocal;
                    var originalWorld = node.WorldMatrix;
                    
                    // Restore corrected transform and get new world transform
                    node.LocalTransform = tempLocal;
                    var correctedWorld = node.WorldMatrix;
                    
                    // Derive mesh bind transform: mesh_bind = IBM_old * joint_world_old
                    var meshBind = oldIbm * originalWorld;
                    
                    // Recalculate IBM: IBM_new = mesh_bind * inverse(joint_world_new)
                    if (Matrix4x4.Invert(correctedWorld, out var invCorrectedWorld))
                    {
                        var newIbm = meshBind * invCorrectedWorld;
                        
                        // Sanitize IBM: According to glTF spec, the fourth row MUST be [0, 0, 0, 1]
                        newIbm.M14 = 0;
                        newIbm.M24 = 0;
                        newIbm.M34 = 0;
                        newIbm.M44 = 1;
                        
                        ibmData[i] = newIbm;
                        ibmRecalculated++;
                    }
                    else
                    {
                        Console.WriteLine($"[lol2gltf] WARNING: Failed to invert corrected world matrix for joint {i} ({node.Name}), keeping original IBM");
                    }
                }
                else
                {
                    Console.WriteLine($"[lol2gltf] WARNING: Failed to invert correction matrix for joint {i} ({node.Name}), keeping original IBM");
                }
            }
            Console.WriteLine($"[lol2gltf] Recalculated {ibmRecalculated} inverse bind matrices based on corrected bone world transforms");

            // Update the accessor with new data
            var bufferView = ibmAccessor.SourceBufferView;
            if (bufferView == null)
            {
                Console.WriteLine("[lol2gltf] ERROR: BufferView is null, cannot update IBMs");
            }
            else
            {
                var bufferContent = bufferView.Content;
                var byteOffset = ibmAccessor.ByteOffset;
                
                // Write modified matrices back to buffer using unsafe code
                // Matrix4x4 is 16 floats = 64 bytes
                var bufferArray = bufferContent.Array;
                var bufferOffset = bufferContent.Offset + byteOffset;
                
                unsafe
                {
                    fixed (Matrix4x4* matrixPtr = ibmData)
                    fixed (byte* bufferPtr = &bufferArray[bufferOffset])
                    {
                        var matrixBytePtr = (byte*)matrixPtr;
                        var byteCount = ibmData.Length * sizeof(Matrix4x4);
                        System.Buffer.MemoryCopy(matrixBytePtr, bufferPtr, byteCount, byteCount);
                    }
                }
                
                // Update accessor bounds after modifying the data
                ibmAccessor.UpdateBounds();
                
                Console.WriteLine($"[lol2gltf] Updated buffer with recalculated inverse bind matrices and recalculated bounds");
            }
        }

        // Step 3: Apply corrections to animation rotations
        var animations = gltf.LogicalAnimations?.ToList();
        if (animations == null || animations.Count == 0)
        {
            Console.WriteLine("[lol2gltf] No animations found, skipping animation rotation corrections");
        }
        else
        {
            Console.WriteLine($"[lol2gltf] Found {animations.Count} animation(s)");
            int animationChannelsCorrected = 0;
            
            foreach (var animation in animations)
            {
                Console.WriteLine($"[lol2gltf] Processing animation: {animation.Name ?? "Unnamed"} with {animation.Channels.Count} channels");
                
                foreach (var channel in animation.Channels)
                {
                    if (channel.TargetNode == null)
                    {
                        Console.WriteLine("[lol2gltf] Channel has no target node, skipping");
                        continue;
                    }
                    
                    if (channel.TargetNodePath != SharpGLTF.Schema2.PropertyPath.rotation)
                    {
                        continue; // Skip non-rotation channels
                    }

                    int jointIdx = jointNodes.IndexOf(channel.TargetNode);
                    if (jointIdx < 0)
                    {
                        Console.WriteLine($"[lol2gltf] Channel target node not found in joints, skipping");
                        continue;
                    }

                    var correctionMatrix = boneCorrectionMatrices.GetValueOrDefault(jointIdx);
                    if (!correctionMatrix.HasValue)
                    {
                        continue; // No correction needed for this bone
                    }

                    // Get rotation sampler
                    var sampler = channel.GetRotationSampler();
                    if (sampler == null)
                    {
                        Console.WriteLine($"[lol2gltf] Channel has no rotation sampler, skipping");
                        continue;
                    }

                    // Get keyframes
                    var keyframes = sampler.GetLinearKeys().ToList();
                    if (keyframes.Count == 0)
                    {
                        Console.WriteLine($"[lol2gltf] Channel has no keyframes, skipping");
                        continue;
                    }

                    Console.WriteLine($"[lol2gltf] Correcting {keyframes.Count} keyframes for bone {jointIdx} ({channel.TargetNode.Name})");

                    // Apply corrections to each keyframe
                    // For animations, we apply the correction directly to the rotation quaternion
                    // This maintains the animation's relationship with the corrected bone orientation
                    var correctedKeyframes = new Dictionary<float, Quaternion>();
                    var correctionQuat = Quaternion.CreateFromRotationMatrix(correctionMatrix.Value);
                    
                    foreach (var (key, quat) in keyframes)
                    {
                        // Apply correction: new_quat = correction_quat * old_quat
                        // This rotates the animation quaternion by the correction
                        var newQuat = Quaternion.Multiply(correctionQuat, quat);
                        correctedKeyframes[key] = newQuat;
                    }

                    // Recreate the rotation channel with corrected keyframes
                    // Note: This replaces the old channel, which is what we want
                    animation.CreateRotationChannel(channel.TargetNode, correctedKeyframes, sampler.InterpolationMode == SharpGLTF.Schema2.AnimationInterpolationMode.LINEAR);
                    animationChannelsCorrected++;
                }
            }

            Console.WriteLine($"[lol2gltf] Applied corrections to {animationChannelsCorrected} animation rotation channels");
        }

        Console.WriteLine($"[lol2gltf] ===== Automatic bone orientation completed =====");
    }
}
